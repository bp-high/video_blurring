#!/usr/bin/env python3
"""Detect sensitive text regions in a screen-recording video.

Multi-scale template matching (handles browser zoom / page scale changes):
  pass 1 sweeps representative frames (1 fps) with the full scale range to
  find which templates are on screen when; pass 2 sweeps the video at 10 fps
  inside those active windows and records every match.

Templates are small PNG crops of the exact strings to redact (account
number, branch name, reference number, ...) taken from the source video.
They are kept out of version control because they contain the very content
being redacted.

Usage:
  python3 detect.py --video INPUT.mp4 --templates DIR --out hits.json
"""
import argparse
import glob
import json
import os
import time

import cv2

THRESH = 0.74
SCALES = [0.70 * (1.06 ** k) for k in range(17)]  # 0.70 .. ~1.78


def load_templates(tdir):
    tpls = {}
    for p in glob.glob(os.path.join(tdir, "*.png")):
        name = os.path.splitext(os.path.basename(p))[0]
        tpls[name] = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if not tpls:
        raise SystemExit(f"no templates found in {tdir}")
    return tpls


def match_one(gray, tpl, scale, thresh):
    th, tw = tpl.shape
    sh, sw = max(1, int(round(th * scale))), max(1, int(round(tw * scale)))
    if sh >= gray.shape[0] or sw >= gray.shape[1] or sh < 6 or sw < 10:
        return []
    st = cv2.resize(tpl, (sw, sh), interpolation=cv2.INTER_AREA)
    res = cv2.matchTemplate(gray, st, cv2.TM_CCOEFF_NORMED)
    hits = []
    r = res.copy()
    for _ in range(8):  # up to 8 occurrences per template per frame
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx < thresh:
            break
        x, y = loc
        hits.append((x, y, sw, sh, float(mx), scale))
        x0, y0 = max(0, x - sw // 2), max(0, y - sh)
        r[y0:y + sh, x0:x + sw] = -1  # suppress neighborhood
    return hits


def nms(hits):
    out = []
    for h in sorted(hits, key=lambda h: -h[4]):
        x, y, w, hh = h[:4]
        keep = True
        for o in out:
            ox, oy, ow, oh = o[:4]
            ix = max(0, min(x + w, ox + ow) - max(x, ox))
            iy = max(0, min(y + hh, oy + oh) - max(y, oy))
            if ix * iy > 0.3 * min(w * hh, ow * oh):
                keep = False
                break
        if keep:
            out.append(h)
    return out


def match_frame(gray, tpl, scales, thresh=THRESH):
    hits = []
    for s in scales:
        hits += match_one(gray, tpl, s, thresh)
    return nms(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--templates", required=True)
    ap.add_argument("--out", default="hits.json")
    ap.add_argument("--tmin", type=float, default=0.0,
                    help="skip content before this time (s)")
    ap.add_argument("--tmax", type=float, default=1e9,
                    help="skip content after this time (s)")
    ap.add_argument("--thresh", type=float, default=THRESH,
                    help="match threshold; lower catches text the browser "
                    "zoom has degraded, at the cost of more false hits "
                    "(constrain those via the blur step's --filters)")
    args = ap.parse_args()

    tpls = load_templates(args.templates)
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)

    # ---- pass 1: 1 fps sweep, full scale range ----
    active = {}  # template -> set of active seconds (dilated +-2 s)
    idx = 0
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = idx / fps
        if idx % int(round(fps)) == 0 and args.tmin <= t <= args.tmax:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for name, tpl in tpls.items():
                if match_frame(gray, tpl, SCALES, thresh=args.thresh):
                    s = active.setdefault(name, set())
                    for d in range(-2, 3):
                        s.add(int(t) + d)
        idx += 1
    print(f"pass1 {time.time() - t0:.0f}s")
    for name, secs in sorted(active.items()):
        print(f"  {name}: t={min(secs)}..{max(secs)}")

    # ---- pass 2: 10 fps sweep inside active windows ----
    cap.release()
    cap = cv2.VideoCapture(args.video)
    hits_out = []
    idx = 0
    t0 = time.time()
    step = max(1, int(round(fps / 10)))
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            t = idx / fps
            names = [nm for nm in tpls if int(t) in active.get(nm, ())]
            if names:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                for nm in names:
                    for h in match_frame(gray, tpls[nm], SCALES,
                                         thresh=args.thresh):
                        x, y, w, hh, sc, s = h
                        hits_out.append(dict(t=round(t, 3), name=nm, x=x, y=y,
                                             w=w, h=hh, score=round(sc, 3), scale=s))
        idx += 1
    cap.release()
    print(f"pass2 {time.time() - t0:.0f}s, {len(hits_out)} hits")
    with open(args.out, "w") as f:
        json.dump(hits_out, f)


if __name__ == "__main__":
    main()
