# RUN_REPORT — sbi-netbanking-redaction

## Task idea

Privacy redaction of a real screen recording is a genuinely long-horizon
agent problem: the agent must *inspect* a 2m13s video (≈4,000 frames),
*inventory* every occurrence of five sensitive strings across seven
distinct screens, *engineer* a detection approach that survives browser
zoom changes (0.99x–1.25x observed), scrolling, a burned-in caption bar
that clips rows at the frame edge, and a mouse cursor that parks on top of
a branch code for ~2 seconds — then *verify its own output* frame by frame
and iterate. A one-shot "detect text and blur it" script fails on every
one of those hard cases; getting to a passing artifact requires state
tracking (where is each string, when), hypothesis formation (why did this
frame leak), and disciplined re-verification.

The task is *not* brittle: any redaction mechanism (blur, pixelation,
solid fill) and any detection approach (template matching, OCR, manual
keyframing) passes, as long as the measured outcomes hold.

## Verifier design (tests/grade.py — fully programmatic, no LLM judging)

Ground truth (`tests/ground_truth.json`) holds 21 sensitive instances with
358 (time, rect, scale) samples — 52 tagged *hard* (mid-zoom, mid-scroll,
caption-clipped, cursor-occluded, and single frames at page-swap
boundaries where the new page's content renders one frame before a
detection pass can lock on) — plus 86 must-stay-visible samples for
pre-masked fields and UI landmarks. Every sample was validated against the
original video (sensitive samples demonstrably match there at NCC ≥ 0.70;
visibility samples at ≥ 0.82).

Reward (written to /logs/verifier/reward.json):

- `functional_correctness` (0.40): per-instance fraction of samples where
  the sensitive patch no longer matches in place (NCC < 0.60, ±8 px).
- `constraint_satisfaction` (0.30): half visibility (pre-masked fields and
  landmarks still match at NCC ≥ 0.80), half over-blur budget (changed
  pixels outside dilated sensitive rects ≤ 2% of the frame on a 2 s grid).
- `robustness` (0.15): coverage restricted to the 45 hard samples.
- `artifact_quality` (0.15): container integrity (resolution, frame count,
  audio duration) + blur-size bounds — a covered rect must be genuinely
  defaced (changed pixels ≥ 12% of the text box) and per-frame changed
  area must stay ≤ 12x the active sensitive area.

Original and candidate are decoded in one lockstep pass, so frames are
index-aligned; there is no seek nondeterminism.

**Pass bar:** overall ≥ 0.90 AND functional_correctness ≥ 0.95.

## Verifier validation (run on 2026-09-01, this container)

| candidate | overall | functional | constraint | robustness | artifact |
|---|---|---|---|---|---|
| oracle output (solution/solve.sh) | **1.0000** | 1.0 | 1.0 | 1.0 (52/52 hard) | 1.0 |
| near-miss: oracle w/o frame-exact cut placement | 0.9640 | 0.9605 | 1.0 | 0.8654 (45/52) | 1.0 |
| unmodified original video | 0.4153 | 0.0185 | 1.0 | 0.0192 | 0.7 |
| cheat: blur the entire frame | 0.6986 | 1.0 | 0.0076 | 1.0 | 0.9755 |

The two shallow directions (do nothing / blur everything) are cleanly
rejected, and the near-miss row shows the verifier resolves even
single-frame leaks at page-swap boundaries — an earlier oracle iteration
that placed its temporal cut points one frame off fails the robustness
criterion. Only targeted, temporally frame-exact redaction reaches the
pass bar.

## Oracle solution

`solution/solve.sh` (≈45 min): multi-scale NCC template detection (17
scales, 10 fps sampling inside active windows, threshold 0.70 with
per-template time/region/score fences), per-location track building with
occlusion gap-bridging, page-swap clamping so temporal padding never
crosses a cut, hand-measured bands for the caption-clipped zoom
transition, pixelate+Gaussian redaction, ffmpeg mux with audio copied.

## Reproduction

```
harbor run -p ./collinear-candidate/sbi-netbanking-redaction -a oracle
harbor run -p ./collinear-candidate/sbi-netbanking-redaction -a <agent> -m <gpt-5.5-high-or-opus-4.7>
harbor view ./jobs
```

Local (no harbor):

```
docker build -f environment/Dockerfile -t sbi-redact .
docker run -v $PWD/tests:/tests -v $PWD/solution:/solution -v /tmp/logs:/logs sbi-redact \
    bash -c "/solution/solve.sh && /tests/test.sh"
cat /tmp/logs/verifier/reward.json
```

## Expected target-model failure modes (to be confirmed with model runs)

1. **Transition leaks** — detecting on sampled frames and blurring only at
   detection times leaves the string readable mid-zoom/mid-scroll; the 45
   hard samples specifically catch this (robustness < 0.7 in our own
   first-iteration pipeline before gap-bridging and band work).
2. **Cursor occlusion** — the mouse parks on `04388` at t≈112–114; naive
   per-frame detection loses the match and un-blurs for ~2 s.
3. **Caption-clipped rows** — at t≈43–47 the branch row rides under the
   caption bar where full-height matching fails; requires either
   edge-tolerant matching or manual keyframing.
4. **Over-blur** — blurring generously (whole rows, whole tables, the
   whole frame) fails the visibility probes and the 2% off-target budget.
5. **Skipped self-verification** — declaring success without re-scanning
   the produced video; the verifier's per-sample checks are unforgiving.

Model-run evidence: to be attached after running the target model via the
harbor harness (API credits per assignment; commands above).

## Provenance and licensing

- Seed video: SBI's own public YouTube demo ("RINB – Transfer of Savings
  Account", State Bank of India, August 2017), 480p re-encode. Used as a
  realistic redaction subject; all "sensitive" values are the demo's own
  staged data, already public.
- Everything else (ground truth, fixtures — small crops of the seed video
  itself — grader, oracle pipeline, configs) was created from scratch for
  this task.

## Limitations

- Ground truth is specific to this exact video file; re-encoding the seed
  would require regenerating fixtures/ground truth.
- The visibility probes cover representative pre-masked fields and
  landmarks, not every pixel of UI; a pathological agent could blur
  unprobed decorative regions within the 2% budget without penalty.
- task.toml field names should be double-checked against the deployed
  Harbor version's schema.
