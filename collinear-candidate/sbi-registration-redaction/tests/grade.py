#!/usr/bin/env python3
"""Programmatic verifier for the sbi-netbanking-redaction task.

Reads the original seed video, the candidate redacted video, and
ground_truth.json, and writes reward.json / reward.txt.

Measures (all template matching is normalized cross-correlation, and all
frame pairs are read in one lockstep sequential pass, so original and
candidate frames are index-aligned):

- functional_correctness: for every ground-truth occurrence of a sensitive
  string (time, rect, scale), the string must no longer match in the
  candidate (NCC < COVERED_MAX inside the rect + margin). Mean over
  instances of their per-sample coverage.
- constraint_satisfaction: (a) pre-censored fields and UI landmarks must
  still match at their positions (NCC >= VISIBLE_MIN); (b) neighbour
  legibility (see below); (c) over-blur budget: on a 2 s grid, changed
  pixels (|candidate - original| > DIFF_T after light smoothing) outside
  the dilated active sensitive rects must stay under BUDGET_FRAC of the
  frame.
- neighbor_legibility: the text immediately adjoining each redaction — the
  field label to its left, the hint or URL parameter to its right, the
  table row above or below — must still match in place. This is what
  separates a redaction sized to its value from one that has crept a few
  pixels into the surrounding page: the over-blur budget is a whole-frame
  measure and a handful of encroaching pixels never troubles it, whereas
  clipping the "is" off a label, or the first column of a "Help?" link,
  fails here. Reported as its own top-level metric so a run can be
  rejected on it directly.
- robustness: coverage restricted to samples tagged "hard" (zoom / scroll
  transitions and cursor-occlusion windows).
- artifact_quality: container integrity (resolution, frame count, audio
  duration) plus blur-size bounds per covered sample: the changed-pixel
  mask must cover >= MIN_COVER of the text rect (a real obscuring patch,
  not a pixel flip) and the frame's total changed area must stay within
  MAX_AREA_X times the active sensitive area (no giant boxes).

overall = 0.40*functional + 0.30*constraint + 0.15*robustness + 0.15*artifact
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _analysis

COVERED_MAX = 0.60   # sensitive text counts as covered below this NCC
VISIBLE_MIN = 0.80   # visibility probe counts as intact above this NCC
DIFF_T = 12          # per-pixel |candidate-original| threshold (grayscale)
BUDGET_FRAC = 0.02   # allowed off-target changed-pixel fraction per frame
MIN_COVER = 0.12     # changed mask must cover this much of a covered rect
                     # (text strokes are ~20-30% of a text box on these white
                     # pages; a 1-px defacement that merely breaks NCC is <5%)
NBR_DIFF_T = 20      # per-pixel threshold for the neighbour check. Computed
                     # on UNSMOOTHED grayscale: the light blur used elsewhere
                     # to suppress codec noise spreads an in-box change a
                     # couple of pixels outward, which would report every
                     # correctly-sized redaction as touching its neighbour.
NBR_TOL = 0.02       # changed-pixel fraction tolerated inside a neighbour
                     # rect. These rects hold text that abuts a redaction but
                     # must survive untouched, so the expectation is zero
                     # change and the tolerance only absorbs re-encode noise.
                     # Checked as changed pixels rather than NCC on purpose:
                     # NCC over a wide crop still scores >0.80 when a few
                     # columns are blurred away, which is exactly the failure
                     # (a label's last letters eaten by an oversized box)
                     # this measure exists to reject.
MAX_AREA_X = 12.0    # frame changed-area cap: X * active sensitive area
MARGIN = 8           # search margin around a ground-truth rect (px)


def ffmpeg_meta(path, ffmpeg):
    p = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True)
    err = p.stderr
    audio = "Audio:" in err
    dur = None
    for line in err.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split()[1].rstrip(",")
            h, m, s = hms.split(":")
            dur = int(h) * 3600 + int(m) * 60 + float(s)
    return audio, dur


def probe(gray, tpl, scale, rect):
    x, y = rect[0], rect[1]
    sh = max(1, int(round(tpl.shape[0] * scale)))
    sw = max(1, int(round(tpl.shape[1] * scale)))
    x1, y1 = max(0, x - MARGIN), max(0, y - MARGIN)
    x2 = min(gray.shape[1], x + sw + MARGIN)
    y2 = min(gray.shape[0], y + sh + MARGIN)
    roi = gray[y1:y2, x1:x2]
    if roi.shape[0] <= sh or roi.shape[1] <= sw:
        return 0.0
    st = cv2.resize(tpl, (sw, sh), interpolation=cv2.INTER_AREA)
    return float(cv2.matchTemplate(roi, st, cv2.TM_CCOEFF_NORMED).max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--out-dir", default=os.environ.get("VERIFIER_LOGS",
                                                        "/logs/verifier"))
    ap.add_argument("--ffmpeg", default=os.environ.get("FFMPEG", "ffmpeg"))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    def finish(reward):
        with open(os.path.join(args.out_dir, "reward.json"), "w") as f:
            json.dump(reward, f, indent=1)
        with open(os.path.join(args.out_dir, "reward.txt"), "w") as f:
            f.write(f"{reward['overall']:.4f}\n")
        print(json.dumps(reward, indent=1))

    gt = json.load(open(args.ground_truth))
    gv = gt["video"]
    zero = dict(overall=0.0, functional_correctness=0.0,
                constraint_satisfaction=0.0, robustness=0.0,
                artifact_quality=0.0)

    # ---- container integrity ----
    cap_c = cv2.VideoCapture(args.candidate)
    if not cap_c.isOpened():
        zero["error"] = "candidate video cannot be opened"
        return finish(zero)
    W = int(cap_c.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap_c.get(cv2.CAP_PROP_FRAME_HEIGHT))
    N = int(cap_c.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap_c.get(cv2.CAP_PROP_FPS)
    if (W, H) != (gv["w"], gv["h"]) or abs(fps - gv["fps"]) > 0.5:
        zero["error"] = f"resolution/fps mismatch: {W}x{H}@{fps}"
        return finish(zero)
    frames_ok = abs(N - gv["frames"]) <= 10
    audio_ok, dur = ffmpeg_meta(args.candidate, args.ffmpeg)
    dur_ok = dur is not None and abs(dur - gv["duration"]) <= 0.6
    cap_c.release()

    tpls = {}
    def tpl(fx):
        if fx not in tpls:
            img = cv2.imread(os.path.join(args.fixtures, fx),
                             cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise SystemExit(f"missing fixture {fx}")
            tpls[fx] = img
        return tpls[fx]

    # ---- collect work per frame index ----
    fps = gv["fps"]
    work = {}  # frame_idx -> dict(redact=[(inst,sample)], visible=[...], budget=bool)
    def slot(t):
        return work.setdefault(int(round(t * fps)), dict(redact=[], visible=[],
                                                         neighbor=[],
                                                         budget=False))
    for inst in gt["redact"]:
        for s in inst["samples"]:
            slot(s["t"])["redact"].append((inst, s))
    for inst in gt["visible"]:
        for s in inst["samples"]:
            slot(s["t"])["visible"].append((inst, s))
    for inst in gt.get("neighbors", []):
        for s in inst["samples"]:
            slot(s["t"])["neighbor"].append((inst, s))
    t = 1.0
    while t < gv["duration"] - 0.5:
        slot(round(t, 2))["budget"] = True
        t += 2.0

    # active sensitive rects per time, for the budget's allowed mask
    def active_rects(t):
        rects = []
        for inst in gt["redact"]:
            for s in inst["samples"]:
                if abs(s["t"] - t) <= 1.0:
                    sh = int(round(tpl(inst["fixture"]).shape[0] * s["scale"]))
                    sw = int(round(tpl(inst["fixture"]).shape[1] * s["scale"]))
                    rects.append((s["x"], s["y"], sw, sh))
        return rects

    # ---- lockstep pass over both videos ----
    cap_o = cv2.VideoCapture(args.original)
    cap_c = cv2.VideoCapture(args.candidate)
    res = dict(cov={}, hard=[0, 0], vis={}, nbr={}, budget=[0, 0],
               minsz=[0, 0], maxsz=[0, 0],
               # state tracking: when and where each expectation was violated
               leaks={}, weak={}, vis_bad={}, nbr_bad={}, budget_bad=[])
    idx = 0
    while True:
        ok_o, fr_o = cap_o.read()
        ok_c, fr_c = cap_c.read()
        if not ok_c or not ok_o:
            break
        w = work.get(idx)
        if w:
            g_c = cv2.cvtColor(fr_c, cv2.COLOR_BGR2GRAY)
            diff = raw_diff = None
            g_o = None
            if w["redact"] or w["budget"] or w["neighbor"]:
                g_o = cv2.cvtColor(fr_o, cv2.COLOR_BGR2GRAY)
            if w["redact"] or w["budget"]:
                a = cv2.GaussianBlur(g_o, (0, 0), 1.2)
                b = cv2.GaussianBlur(g_c, (0, 0), 1.2)
                diff = (cv2.absdiff(a, b) > DIFF_T)
            if w["neighbor"]:
                raw_diff = (cv2.absdiff(g_o, g_c) > NBR_DIFF_T)
            for inst, s in w["redact"]:
                sc = probe(g_c, tpl(inst["fixture"]), s["scale"],
                           (s["x"], s["y"]))
                covered = sc < COVERED_MAX
                c = res["cov"].setdefault(inst["id"], [0, 0])
                c[1] += 1
                c[0] += covered
                if not covered:
                    res["leaks"].setdefault(inst["id"], []).append(
                        round(idx / fps, 3))
                if s.get("hard"):
                    res["hard"][1] += 1
                    res["hard"][0] += covered
                if covered:
                    sh = int(round(tpl(inst["fixture"]).shape[0] * s["scale"]))
                    sw = int(round(tpl(inst["fixture"]).shape[1] * s["scale"]))
                    y2, x2 = min(H, s["y"] + sh), min(W, s["x"] + sw)
                    region = diff[s["y"]:y2, s["x"]:x2]
                    res["minsz"][1] += 1
                    strong = region.size > 0 and region.mean() >= MIN_COVER
                    res["minsz"][0] += strong
                    if not strong:
                        res["weak"].setdefault(inst["id"], []).append(
                            round(idx / fps, 3))
            if w["redact"]:
                acts = active_rects(idx / fps)
                area = sum(w_ * h_ for (_, _, w_, h_) in acts) + 4000
                res["maxsz"][1] += 1
                res["maxsz"][0] += int(diff.sum()) <= MAX_AREA_X * area
            for inst, s in w["visible"]:
                sc = probe(g_c, tpl(inst["fixture"]), s["scale"],
                           (s["x"], s["y"]))
                v = res["vis"].setdefault(inst["id"], [0, 0])
                v[1] += 1
                v[0] += sc >= VISIBLE_MIN
                if sc < VISIBLE_MIN:
                    res["vis_bad"].setdefault(inst["id"], []).append(
                        round(idx / fps, 3))
            for inst, s in w["neighbor"]:
                x2n, y2n = min(W, s["x"] + s["w"]), min(H, s["y"] + s["h"])
                region = raw_diff[s["y"]:y2n, s["x"]:x2n]
                untouched = region.size > 0 and region.mean() <= NBR_TOL
                sc = probe(g_c, tpl(inst["fixture"]), s["scale"],
                           (s["x"], s["y"]))
                n = res["nbr"].setdefault(inst["id"], [0, 0])
                n[1] += 1
                ok_n = bool(untouched and sc >= VISIBLE_MIN)
                n[0] += ok_n
                if not ok_n:
                    res["nbr_bad"].setdefault(inst["id"], []).append(
                        round(idx / fps, 3))
            if w["budget"]:
                allowed = np.zeros((H, W), bool)
                for (x, y, w_, h_) in active_rects(idx / fps):
                    d = 28
                    allowed[max(0, y - d):y + h_ + d,
                            max(0, x - d):x + w_ + d] = True
                off = int((diff & ~allowed).sum())
                res["budget"][1] += 1
                within = off <= BUDGET_FRAC * W * H
                res["budget"][0] += within
                if not within:
                    res["budget_bad"].append(round(idx / fps, 3))
        idx += 1
    cap_o.release()
    cap_c.release()

    inst_scores = {k: c[0] / c[1] for k, c in res["cov"].items()}
    functional = float(np.mean(list(inst_scores.values()))) if inst_scores else 0.0
    vis_scores = {k: v[0] / v[1] for k, v in res["vis"].items()}
    score_v = float(np.mean(list(vis_scores.values()))) if vis_scores else 0.0
    nbr_scores = {k: v[0] / v[1] for k, v in res["nbr"].items()}
    score_b = res["budget"][0] / max(1, res["budget"][1])
    if nbr_scores:
        score_n = float(np.mean(list(nbr_scores.values())))
        constraint = 0.4 * score_v + 0.3 * score_n + 0.3 * score_b
    else:
        score_n = None          # task ships no neighbour probes
        constraint = 0.5 * score_v + 0.5 * score_b
    robustness = res["hard"][0] / max(1, res["hard"][1])
    integrity = (frames_ok + audio_ok + dur_ok) / 3.0
    min_ok = res["minsz"][0] / max(1, res["minsz"][1])
    max_ok = res["maxsz"][0] / max(1, res["maxsz"][1])
    artifact = 0.4 * integrity + 0.3 * min_ok + 0.3 * max_ok
    overall = (0.40 * functional + 0.30 * constraint +
               0.15 * robustness + 0.15 * artifact)
    # Harbor parses reward.json straight into VerifierResult.rewards, typed
    # dict[str, float | int]: every value must be a scalar and no key may be
    # null, so the detail tables and the findings ride in analysis.json.
    #
    # "reward" duplicates "overall" on purpose. Harbor treats a key by that
    # exact name as the headline score (viewer/server.py, cli/jobs.py
    # _primary_reward); with several keys and none of them called "reward" it
    # gives up and `harbor view` shows the trial's Outcome as "-".
    reward = dict(reward=round(overall, 4),
                overall=round(overall, 4),
                functional_correctness=round(functional, 4),
                constraint_satisfaction=round(constraint, 4),
                robustness=round(robustness, 4),
                artifact_quality=round(artifact, 4))
    if score_n is not None:
        reward["neighbor_legibility"] = round(score_n, 4)
    detail = dict(instances={k: round(v, 3) for k, v in inst_scores.items()},
                  visible={k: round(v, 3) for k, v in vis_scores.items()},
                  neighbors={k: round(v, 3) for k, v in nbr_scores.items()},
                  budget_frames=f"{res['budget'][0]}/{res['budget'][1]}",
                  hard=f"{res['hard'][0]}/{res['hard'][1]}",
                  blur_min_size=f"{res['minsz'][0]}/{res['minsz'][1]}",
                  blur_max_size=f"{res['maxsz'][0]}/{res['maxsz'][1]}",
                  frames_ok=frames_ok, audio_ok=audio_ok,
                  duration_ok=dur_ok)
    analysis = _analysis.build(gt, res, fps, {
        k: reward[k] for k in ("overall", "functional_correctness",
                               "constraint_satisfaction", "robustness",
                               "artifact_quality", "neighbor_legibility")
        if reward.get(k) is not None})
    analysis["detail"] = detail
    with open(os.path.join(args.out_dir, "analysis.json"), "w") as f:
        json.dump(analysis, f, indent=1)
    with open(os.path.join(args.out_dir, "analysis.md"), "w") as f:
        f.write(_analysis.to_markdown(analysis, reward))
    finish(reward)


if __name__ == "__main__":
    main()
