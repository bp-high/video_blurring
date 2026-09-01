#!/usr/bin/env python3
"""Frame-exact detector for screen recordings whose pages do not move.

Where `detect.py` sweeps the whole frame at many scales (needed when a
recording pans, scrolls and zooms), this detector is for recordings that
navigate between static pages: each sensitive string is declared once with
the region it occupies, and the detector answers a narrower question —
*on which frames is it actually on screen?* — by matching the string's
template inside a small window around that region, on EVERY frame.

That yields frame-exact appearance/disappearance times (text typed into a
form, a page swapped out), which is what keeps redaction from either
lagging a page change or lingering past it.

Spec (JSON list), one entry per sensitive string:
  {
    "id": "acct",                  # unique
    "template": "acct.png",        # crop of the string, in --templates
    "f1": 2150, "f2": 2704,        # frame window to search (a page/scene)
    "x": 264, "y": 116,            # where the string sits on that page
    "margin": 24,                  # search slack around (x, y), px
    "thresh": 0.75,                # match threshold (NCC)
    "box": [439, 236, 553, 253],   # OPTIONAL explicit blur box (x1,y1,x2,y2)
    "pad": [5, 4],                 # else template rect + this padding
    "follows": "c_name"            # OPTIONAL: reuse that item's interval
                                   # (for strings too generic to match, e.g.
                                   # a lone "1", that share a static page)
  }

Writes intervals in blur.py's --extra format: [{t1,t2,x1,y1,x2,y2,id}, ...]

Usage:
  python3 detect_static.py --video V.mp4 --templates DIR --spec spec.json \
      --out intervals.json [--report report.json]
"""
import argparse
import json
import os

import cv2


def match_at(gray, tpl, x, y, margin, scales=(1.0,)):
    """Best NCC for tpl near (x, y). Returns (score, mx, my, scale)."""
    best = (0.0, x, y, 1.0)
    H, W = gray.shape
    for s in scales:
        th = max(1, int(round(tpl.shape[0] * s)))
        tw = max(1, int(round(tpl.shape[1] * s)))
        st = tpl if s == 1.0 else cv2.resize(tpl, (tw, th),
                                             interpolation=cv2.INTER_AREA)
        x1, y1 = max(0, x - margin), max(0, y - margin)
        x2, y2 = min(W, x + tw + margin), min(H, y + th + margin)
        roi = gray[y1:y2, x1:x2]
        if roi.shape[0] <= th or roi.shape[1] <= tw:
            continue
        res = cv2.matchTemplate(roi, st, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (float(mx), x1 + loc[0], y1 + loc[1], s)
    return best


def runs_from_frames(frames, max_gap):
    """Group sorted frame numbers into runs, bridging gaps <= max_gap."""
    out = []
    for f in frames:
        if out and f - out[-1][1] <= max_gap:
            out[-1][1] = f
        else:
            out.append([f, f])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--templates", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report")
    ap.add_argument("--max-gap", type=int, default=3,
                    help="bridge holes of at most this many frames inside a "
                         "run (a cursor crossing the text, a repaint)")
    ap.add_argument("--min-run", type=int, default=2,
                    help="discard runs shorter than this many frames")
    args = ap.parse_args()

    spec = json.load(open(args.spec))
    tpls = {}
    for it in spec:
        if "template" in it and it["template"] not in tpls:
            p = os.path.join(args.templates, it["template"])
            img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise SystemExit(f"missing template {p}")
            tpls[it["template"]] = img

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    # frame -> items to test on it
    per_frame = {}
    for it in spec:
        if it.get("follows"):
            continue
        for f in range(it["f1"], it["f2"] + 1):
            per_frame.setdefault(f, []).append(it)

    hits = {it["id"]: [] for it in spec if not it.get("follows")}
    scores = {it["id"]: [] for it in spec if not it.get("follows")}
    idx = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        items = per_frame.get(idx)
        if items:
            gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            for it in items:
                sc, mx, my, s = match_at(gray, tpls[it["template"]],
                                         it["x"], it["y"],
                                         it.get("margin", 24),
                                         it.get("scales", (1.0,)))
                if sc >= it.get("thresh", 0.75):
                    hits[it["id"]].append((idx, mx, my, sc))
                scores[it["id"]].append(round(sc, 3))
        idx += 1
    cap.release()

    by_id = {it["id"]: it for it in spec}
    intervals = []
    report = {}
    computed = {}
    for it in spec:
        if it.get("follows"):
            continue
        hs = hits[it["id"]]
        frames = [h[0] for h in hs]
        rs = [r for r in runs_from_frames(frames, args.max_gap)
              if r[1] - r[0] + 1 >= args.min_run]
        computed[it["id"]] = rs
        report[it["id"]] = dict(
            frames_matched=len(frames), runs=rs,
            times=[[round(a / fps, 3), round(b / fps, 3)] for a, b in rs],
            score_max=max(scores[it["id"]], default=0),
            score_min_in_run=min((h[3] for h in hs), default=None),
            pos_spread=[max((h[1] for h in hs), default=0) -
                        min((h[1] for h in hs), default=0),
                        max((h[2] for h in hs), default=0) -
                        min((h[2] for h in hs), default=0)])

    for it in spec:
        src = it.get("follows") or it["id"]
        for a, b in computed.get(src, []):
            if "box" in it:
                x1, y1, x2, y2 = it["box"]
            else:
                tpl = tpls[it["template"]]
                px, py = it.get("pad", [5, 4])
                x1, y1 = it["x"] - px, it["y"] - py
                x2 = it["x"] + tpl.shape[1] + px
                y2 = it["y"] + tpl.shape[0] + py
            intervals.append(dict(id=it["id"],
                                  t1=round((a - 0.5) / fps, 4),
                                  t2=round((b + 0.5) / fps, 4),
                                  x1=int(x1), y1=int(y1),
                                  x2=int(x2), y2=int(y2)))

    json.dump(intervals, open(args.out, "w"), indent=1)
    print(f"{len(intervals)} intervals -> {args.out}")
    for k, v in report.items():
        print(f"  {k}: runs={v['runs']} t={v['times']} "
              f"score_max={v['score_max']} spread={v['pos_spread']}")
    if args.report:
        json.dump(report, open(args.report, "w"), indent=1)


if __name__ == "__main__":
    main()
