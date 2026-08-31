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

ASSOC = 0.25         # associate hits to frames within this window (s)
EDGE_EXT = 0.3       # extend blur beyond first/last hit of a run (s)
PAD_FRAC = 0.06      # spatial padding fraction
PAD_MIN = 5          # spatial padding minimum (px)

# For this template, also blur the rest of its table row (the history table
# row carries account number, branch codes and date to the right of the
# reference-number cell).
ROW_EXT_TEMPLATE = "refno"
ROW_EXT_FACTOR = 5.4  # extra width, in units of matched width


def padded(x, y, w, h, W, H, frac=PAD_FRAC):
    px = max(PAD_MIN, int(w * frac))
    py = max(PAD_MIN, int(h * frac))
    return (max(0, x - px), max(0, y - py),
            min(W, x + w + px), min(H, y + h + py))


def hit_rects(h, W, H):
    """Padded rects for one hit. The row-extension rect gets only minimal
    padding so it doesn't bleed into neighbouring page elements."""
    rects = [padded(h["x"], h["y"], h["w"], h["h"], W, H)]
    if h["name"] == ROW_EXT_TEMPLATE:
        rects.append(padded(h["x"], h["y"], int(h["w"] * ROW_EXT_FACTOR),
                            h["h"], W, H, frac=0.0))
    return rects


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if inter == 0:
        return 0.0
    aa = (a[2] - a[0]) * (a[3] - a[1])
    ab = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(aa + ab - inter)


GAP_FILL = 3.5       # bridge match gaps at a stable location (s), e.g. when
                     # the mouse cursor parks on the text and breaks the match


def build_schedule(hits, W, H, cuts=()):
    """Return list of blur events (t_start, t_end, rect).

    Hits are grouped per template into location tracks (a hit joins the
    track whose latest rect it overlaps). Within a track, gaps up to
    GAP_FILL are bridged — a match hole at a stable location means an
    occlusion (e.g. the mouse cursor parked on the text), not absence —
    and the track's run edges get EDGE_EXT of temporal padding. A stray
    false hit elsewhere on the page lands in its own track and cannot
    break another track's bridging.

    `cuts` is a sorted list of hard page-swap times: every event is
    clipped to the cut segment its source hit lies in, and no gap is
    bridged across a cut, so temporal padding never paints blur onto the
    page shown before or after a swap.
    """
    def seg(t):
        lo, hi = -1e9, 1e9
        for c in cuts:
            if c <= t:
                lo = c
            else:
                hi = c
                break
        return lo, hi

    events = []

    def emit(t1, t2, th, rect):
        lo, hi = seg(th)
        t1, t2 = max(t1, lo), min(t2, hi - 1e-3)
        if t1 < t2:
            events.append((t1, t2, rect))

    by_name = {}
    for h in hits:
        by_name.setdefault(h["name"], []).append(h)

    for name, hs in by_name.items():
        hs.sort(key=lambda h: h["t"])
        tracks = []  # each: list of hits
        for h in hs:
            base = padded(h["x"], h["y"], h["w"], h["h"], W, H)
            for tr in tracks:
                p = tr[-1]
                if iou(base, padded(p["x"], p["y"], p["w"], p["h"], W, H)) >= 0.3:
                    tr.append(h)
                    break
            else:
                tracks.append([h])
        for tr in tracks:
            for h in tr:
                for r in hit_rects(h, W, H):
                    emit(h["t"] - ASSOC, h["t"] + ASSOC, h["t"], r)
            for a, b in zip(tr, tr[1:]):
                rects_a, rects_b = hit_rects(a, W, H), hit_rects(b, W, H)
                if b["t"] - a["t"] <= GAP_FILL and seg(a["t"]) == seg(b["t"]):
                    for ra, rb in zip(rects_a, rects_b):
                        union = (min(ra[0], rb[0]), min(ra[1], rb[1]),
                                 max(ra[2], rb[2]), max(ra[3], rb[3]))
                        emit(a["t"], b["t"], a["t"], union)
                else:  # run boundary inside the track
                    for ra in rects_a:
                        emit(a["t"], a["t"] + EDGE_EXT, a["t"], ra)
                    for rb in rects_b:
                        emit(b["t"] - EDGE_EXT, b["t"], b["t"], rb)
            for r in hit_rects(tr[0], W, H):
                emit(tr[0]["t"] - EDGE_EXT, tr[0]["t"], tr[0]["t"], r)
            for r in hit_rects(tr[-1], W, H):
                emit(tr[-1]["t"], tr[-1]["t"] + EDGE_EXT, tr[-1]["t"], r)
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
    ap.add_argument("--clamp-end", type=float, default=None,
                    help="no blur at or after this time (s), e.g. the hard "
                    "cut where the recorded page gives way to an outro")
    ap.add_argument("--cuts", help="JSON file with a sorted list of hard "
                    "page-swap times (s); temporal padding and gap bridging "
                    "never cross these boundaries")
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
    cuts = ()
    if args.cuts:
        with open(args.cuts) as f:
            cuts = sorted(json.load(f))
    events = build_schedule(hits, W, H, cuts)
    if args.extra:
        with open(args.extra) as f:
            for e in json.load(f):
                events.append((e["t1"], e["t2"],
                               (e["x1"], e["y1"], e["x2"], e["y2"])))
    if args.clamp_end is not None:
        events = [(t1, min(t2, args.clamp_end), r) for (t1, t2, r) in events
                  if t1 < args.clamp_end]
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
