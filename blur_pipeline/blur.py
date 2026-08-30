#!/usr/bin/env python3
"""Render a redacted video from detection hits.

Every detected region is pixelated + Gaussian-blurred, with spatial padding
and temporal padding (blur starts slightly before a string appears and ends
slightly after it leaves), then the original audio track is muxed back in
losslessly via ffmpeg.

Usage:
  python3 blur.py --video INPUT.mp4 --hits hits.json --out OUTPUT.mp4
"""
import argparse
import json
import os
import subprocess

import cv2

SAMPLE_DT = 0.1      # detection sampling step (10 fps)
ASSOC = 0.25         # associate hits to frames within this window (s)
EDGE_EXT = 0.6       # extend blur beyond first/last hit of an interval (s)
GAP_MERGE = 0.9      # bridge gaps in a template's hit timeline (s)
PAD_FRAC = 0.14      # spatial padding fraction
PAD_MIN = 7          # spatial padding minimum (px)

# For this template, also blur the rest of its table row (the history table
# row carries account number, branch codes and date to the right of the
# reference-number cell).
ROW_EXT_TEMPLATE = "refno"
ROW_EXT_FACTOR = 5.4  # extra width, in units of matched width


def padded(x, y, w, h, W, H):
    px = max(PAD_MIN, int(w * PAD_FRAC))
    py = max(PAD_MIN, int(h * PAD_FRAC))
    return (max(0, x - px), max(0, y - py),
            min(W, x + w + px), min(H, y + h + py))


def hit_rects(h):
    rects = [(h["x"], h["y"], h["w"], h["h"])]
    if h["name"] == ROW_EXT_TEMPLATE:
        rects.append((h["x"], h["y"], int(h["w"] * ROW_EXT_FACTOR), h["h"]))
    return rects


def build_schedule(hits, W, H):
    """Return list of blur events (t_start, t_end, rect)."""
    by_name = {}
    for h in hits:
        by_name.setdefault(h["name"], []).append(h)

    events = []
    for name, hs in by_name.items():
        hs.sort(key=lambda h: h["t"])
        for h in hs:
            for r in hit_rects(h):
                events.append((h["t"] - ASSOC, h["t"] + ASSOC, padded(*r, W, H)))
        # extend before the first and after the last hit of contiguous runs
        runs = []
        start = prev = hs[0]
        for h in hs[1:]:
            if h["t"] - prev["t"] > GAP_MERGE:
                runs.append((start, prev))
                start = h
            prev = h
        runs.append((start, prev))
        for a, b in runs:
            for h, (t1, t2) in ((a, (a["t"] - EDGE_EXT, a["t"])),
                                (b, (b["t"], b["t"] + EDGE_EXT))):
                for r in hit_rects(h):
                    events.append((t1, t2, padded(*r, W, H)))
    return events


def anonymize(frame, rect):
    x1, y1, x2, y2 = rect
    roi = frame[y1:y2, x1:x2]
    h, w = roi.shape[:2]
    if h < 2 or w < 2:
        return
    small = cv2.resize(roi, (max(1, w // 14), max(1, h // 12)),
                       interpolation=cv2.INTER_AREA)
    big = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    big = cv2.GaussianBlur(big, (0, 0), sigmaX=max(2.0, h / 5.0))
    frame[y1:y2, x1:x2] = big


def apply_filters(hits, filters):
    """Keep a hit only if it satisfies its template's constraints, if any.
    Constraint keys: tmin, tmax, xmin, xmax, ymin, ymax, min_score."""
    out = []
    for h in hits:
        c = filters.get(h["name"])
        if c is None:
            out.append(h)
            continue
        if (c.get("tmin", -1e9) <= h["t"] <= c.get("tmax", 1e9)
                and c.get("xmin", -1e9) <= h["x"] <= c.get("xmax", 1e9)
                and c.get("ymin", -1e9) <= h["y"] <= c.get("ymax", 1e9)
                and h["score"] >= c.get("min_score", 0)):
            out.append(h)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--hits", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--filters", help="JSON file of per-template hit "
                    "constraints, for templates that also match unrelated UI")
    ap.add_argument("--extra", help="JSON file of manual blur events "
                    "[{t1,t2,x1,y1,x2,y2},...] for regions template matching "
                    "cannot reach (e.g. rows clipped by a caption overlay)")
    args = ap.parse_args()

    with open(args.hits) as f:
        hits = json.load(f)
    if args.filters:
        with open(args.filters) as f:
            n0 = len(hits)
            hits = apply_filters(hits, json.load(f))
            print(f"filtered hits {n0} -> {len(hits)}")
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    events = build_schedule(hits, W, H)
    if args.extra:
        with open(args.extra) as f:
            for e in json.load(f):
                events.append((e["t1"], e["t2"],
                               (e["x1"], e["y1"], e["x2"], e["y2"])))
    print(f"{len(events)} blur events; video {W}x{H}@{fps}")

    cmd = [args.ffmpeg, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-",
           "-i", args.video,
           "-map", "0:v", "-map", "1:a?",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "copy",
           "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    idx = nblur = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = idx / fps
        applied = False
        for (t1, t2, rect) in events:
            if t1 <= t <= t2:
                anonymize(frame, rect)
                applied = True
        nblur += applied
        proc.stdin.write(frame.tobytes())
        idx += 1
    proc.stdin.close()
    proc.wait()
    cap.release()
    print(f"done: {idx} frames, {nblur} with blur, rc={proc.returncode}")


if __name__ == "__main__":
    main()
