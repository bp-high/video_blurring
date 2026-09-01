# RUN_REPORT — sbi-registration-redaction

## Task idea

A privacy scrub is only as good as the inspection behind it. This
recording of SBI's public internet-banking registration walkthrough shows
**live, unmasked** customer data — account number, CIF, mobile, a debit
card with cardholder name and expiry, a bank-issued temporary username,
and transaction identifiers — spread across seven pages of a 3m06s
session. Finding and covering all of it requires an agent to inventory a
whole timeline rather than a handful of sampled screens, and to notice
that the page does not always show what it showed a second ago.

Two properties make it long-horizon rather than fiddly:

1. **The card fields are re-rendered mid-page.** When Submit is pressed on
   the payment gateway, the PAN and cardholder name are replaced in place
   by their tokenized/hashed forms (`1a33ba1f6389c624…`,
   `8af8994174d2b6042c…`) while "Processing… Please wait" is shown — for
   0.7 s, 21 frames, on a page whose URL and layout never change. An agent
   that inspects the page once, redacts what it saw and moves on leaves
   derived card data on screen. Nothing announces this; it has to be found
   by looking at the page across its whole lifetime.
2. **Values appear and vanish on a single frame.** The recording is
   spliced: the registration form is empty at frame 2296 and fully
   populated at 2297; the card form likewise at 3958/3959. Redaction has
   to be frame-exact in both directions — a pipeline that samples at 1 or
   10 fps and pads its intervals either leaks a frame or paints blur onto
   an empty form.

Add to that identifiers hidden in URL query strings (easy to overlook
entirely) and a set of values that must be *left alone* — the site's own
masked card number, the PIN dots, the captchas — and the task rewards
inspection discipline over pattern-matching.

The task is not brittle: any redaction mechanism and any detection
approach passes, provided the measured outcomes hold.

## Verifier design (tests/grade.py — fully programmatic, no LLM judging)

Ground truth (`tests/ground_truth.json`) holds 19 sensitive instances with
467 (time, rect, scale) samples — 236 tagged *hard* (the tokenized-card
window, every interval's first and last frame, and the URL identifiers) —
plus 180 must-stay-visible samples across 16 probes (site-masked card
number, PIN dots, both captchas, field labels, hint text, merchant and
amount, the `Help?` link, the readable parts of URLs, the payment-gateway
domain). Every sample was validated against the original video: sensitive
samples match there at NCC ≥ 0.75, visibility probes at ≥ 0.82. Zero
samples were dropped in validation.

Reward (written to /logs/verifier/reward.json):

- `functional_correctness` (0.40): per-instance fraction of samples where
  the value no longer matches in place (NCC < 0.60, ±8 px).
- `constraint_satisfaction` (0.30): half visibility (probes still match at
  NCC ≥ 0.80), half over-blur budget (changed pixels outside dilated
  sensitive rects ≤ 2% of the frame, on a 2 s grid).
- `robustness` (0.15): coverage restricted to the 236 hard samples.
- `artifact_quality` (0.15): container integrity (resolution, frame count,
  audio duration) + blur-size bounds — a covered rect must be genuinely
  defaced (changed pixels ≥ 12% of the text box) and per-frame changed
  area must stay ≤ 12x the active sensitive area.

Original and candidate are decoded in one lockstep pass, so frames are
index-aligned; there is no seek nondeterminism.

**Pass bar:** overall ≥ 0.90 AND functional_correctness ≥ 0.95.

## Verifier validation (run 2026-09-01, this container)

| candidate | overall | functional | constraint | robustness | artifact | verdict |
|---|---|---|---|---|---|---|
| oracle output (solution/solve.sh) | **1.0000** | 1.0 | 1.0 | 1.0 (236/236) | 1.0 | pass |
| near-miss: redacts the visible card data, misses the tokenized window | 0.9541 | **0.8947** | 1.0 | 0.9746 (230/236) | 1.0 | **fail** |
| unmodified original video | 0.4050 | 0.0 | 1.0 | 0.0 | 0.7 | fail |
| cheat: blur the entire frame | 0.6996 | 1.0 | **0.0** | 1.0 | 0.9976 | fail |

The near-miss row is the point of the task. It is a *thorough* solution —
every value visible on every page is covered, frame-exactly, with no
over-blur — and it still fails, on exactly the two instances
(`cardnum_tok`, `cardname_tok`) that only exist for 21 frames after a
button press. Overall (0.954) even clears the 0.90 line; the
functional-correctness floor is what rejects it. The two shallow
directions (do nothing / blur everything) are rejected far more bluntly.

## Oracle solution

`solution/solve.sh` (~6–8 min): `detect_static.py` matches each declared
value inside a small window around its known position on **every frame**
of the page that shows it, producing frame-exact appearance/disappearance
intervals; `blur.py` renders those intervals with pixelate+Gaussian
redaction and muxes the original audio unchanged. The tokenized card
values are declared as their own items, so their intervals are found the
same way as everything else — the oracle's discovery of them is recorded
in `assets/items.json`, not hardcoded into the renderer.

Note the shape of the oracle: for a recording of static pages the hard
part is *knowing what to look for and when*, so the pipeline is a
declarative item list plus a frame-exact presence detector — deliberately
different machinery from the sibling `sbi-netbanking-redaction` task,
whose recording pans and zooms and needs multi-scale tracking.

## Reproduction

```
harbor run -p ./collinear-candidate/sbi-registration-redaction -a oracle
harbor run -p ./collinear-candidate/sbi-registration-redaction -a <agent> -m <gpt-5.5-high-or-opus-4.7>
harbor view ./jobs
```

Local (no harbor):

```
docker build -f environment/Dockerfile -t sbi-reg-redact .
docker run -v $PWD/tests:/tests -v $PWD/solution:/solution -v /tmp/logs:/logs sbi-reg-redact \
    bash -c "/solution/solve.sh && /tests/test.sh"
cat /tmp/logs/verifier/reward.json
```

## Expected target-model failure modes (to be confirmed with model runs)

1. **The tokenized card window** — the headline trap; demonstrated above to
   cost a pass even when everything else is perfect.
2. **URL identifiers** — `paymentId`, `auth`, `ref`, `trackid` sit in the
   address bar in small type; models that reason about "form fields" miss
   them.
3. **Frame-exactness** — sampling at 1 fps and padding intervals either
   leaks the appearance frame or paints blur over the empty form (which
   the visibility probes and over-blur budget then penalise).
4. **Over-blurring the masked values** — redacting `************ 4567`,
   the PIN dots or a captcha "to be safe" fails constraint satisfaction.
5. **Skipped self-verification** — declaring success without re-scanning
   the produced video.

Model-run evidence: to be attached after running the target model through
the harbor harness (API credits per the assignment; commands above).

## Provenance and licensing

- Seed video: SBI's own public YouTube walkthrough for online internet-
  banking registration. Used as a realistic redaction subject.
- Everything else — the item declarations, ground truth, fixtures (crops
  of the seed video itself), grader, and the `detect_static.py` oracle —
  was created from scratch for this task. `grade.py` is shared with the
  sibling `sbi-netbanking-redaction` task; the ground truth and fixtures
  are entirely this video's.
- The redacted output of this task is published in this repository at
  `output/sbi_registration_redacted.mp4`.

## Limitations

- Ground truth is tied to this exact encode; re-encoding the seed would
  require regenerating fixtures and ground truth.
- Visibility probes cover 16 representative regions, not every pixel of
  UI; an agent could blur an unprobed decorative region within the 2%
  budget without penalty.
- `task.toml` field names should be checked against the deployed Harbor
  version's schema.
