#!/usr/bin/env python3
"""Verify a redacted video: re-run every sensitive-text template against the
output at 10 fps over the full detection scale range. Any match at the
detection threshold means a string survived redaction.

Usage:
  python3 verify.py --video BLURRED.mp4 --templates DIR
"""
import argparse
import time

import cv2

from detect import THRESH, SCALES, load_templates, match_frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--templates", required=True)
    ap.add_argument("--skip", nargs="*", default=[],
                    help="template names to skip (e.g. ones that match "
                         "decorative UI textures)")
    args = ap.parse_args()

    tpls = {k: v for k, v in load_templates(args.templates).items()
            if k not in args.skip}
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    step = max(1, int(round(fps / 10)))
    idx = leaks = 0
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            t = idx / fps
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for nm, tpl in tpls.items():
                for h in match_frame(gray, tpl, SCALES, thresh=THRESH):
                    leaks += 1
                    print(f"LEAK t={t:.2f} {nm} {h[:5]}", flush=True)
        idx += 1
    cap.release()
    print(f"checked {idx} frames in {time.time() - t0:.0f}s; {leaks} leaks")


if __name__ == "__main__":
    main()
