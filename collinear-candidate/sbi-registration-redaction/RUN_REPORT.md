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

Ground truth (`tests/ground_truth.json`) holds 17 sensitive instances with
396 (time, rect, scale) samples — 192 tagged *hard* (the tokenized-card
window, every interval's first and last frame, and the URL identifiers) —
plus 209 must-stay-visible samples across 18 probes (site-masked card
number, PIN dots, both captchas, field labels, hint text, merchant and
amount, the Track ID and its URL counterpart, the `Help?` link, the
readable parts of URLs, the payment-gateway domain) and 192 neighbour
samples across 18 probes. It also carries the recording's 14 page
segments, which the analysis uses as its state timeline. Every sample was
validated against the original video: sensitive samples match there at
NCC ≥ 0.75, visibility and neighbour probes at ≥ 0.82. Zero samples were
dropped in validation.

### What counts as PII here

The task draws an explicit line, and the verifier scores both sides of it.
**Sensitive** (redact): account number, CIF, branch code and registered
mobile; card number, cardholder name and expiry, including the tokenized
forms the gateway substitutes after Submit; the bank-issued temporary
username; and the payment/`auth`/`ref` identifiers in URL query strings.
**Not sensitive** (must stay legible): values the site already masks
(`************ 4567`, the PIN dots), the captchas, page labels and hints,
merchant and amount, the readable parts of URLs — and the **Track ID**,
which is the merchant's own order reference displayed beside Merchant /
Website / Amount. An earlier iteration of this task redacted Track ID on
the reasoning that it is a transaction reference; review corrected that —
it identifies an order, not the customer — so it is now a legibility probe
and blurring it is scored as over-redaction.

Reward (written to /logs/verifier/reward.json):

- `functional_correctness` (0.40): per-instance fraction of samples where
  the value no longer matches in place (NCC < 0.60, ±8 px).
- `constraint_satisfaction` (0.30): 0.4 visibility (probes still match at
  NCC ≥ 0.80) + 0.3 neighbour legibility + 0.3 over-blur budget (changed
  pixels outside dilated sensitive rects ≤ 2% of the frame, on a 2 s grid).
- `neighbor_legibility` (reported separately, and a pass condition in its
  own right): 20 probes on the text abutting a redaction — the label left
  of each field, the hint or URL parameter right of it, the rows above and
  below on the confirmation page, the browser's search icon beside the
  last URL parameter. Each must be left **pixel-untouched**: the check is
  changed pixels (unsmoothed, threshold 20, tolerance 2% of the probe
  rect), not NCC, because NCC over a wide crop still scores above 0.80
  when a few columns have been blurred away — which is precisely the
  defect being hunted. Being pixel-based it also localises the fault: the
  failing probe names the neighbour that was clipped.
- `robustness` (0.15): coverage restricted to the 192 hard samples.
- `artifact_quality` (0.15): container integrity (resolution, frame count,
  audio duration) + blur-size bounds — a covered rect must be genuinely
  defaced (changed pixels ≥ 12% of the text box) and per-frame changed
  area must stay ≤ 12x the active sensitive area.

Original and candidate are decoded in one lockstep pass, so frames are
index-aligned; there is no seek nondeterminism.

### State tracking and failure analysis

Alongside the reward the verifier writes `analysis.json` and
`analysis.md`, so a model run can be analysed without re-watching the
video:

- **PII inventory** — every sensitive item with its plain-English label,
  category (`account_identifier`, `cardholder_data`,
  `cardholder_data_derived`, `personal_name`, `credential`,
  `transaction_identifier`, …), the page it belongs to, why it is
  sensitive, and the exact intervals it is on screen. Paired with a
  **not-PII** table giving, for each thing that must stay legible, the
  reason it is not redacted.
- **State timeline** — one row per page of the recording: how many
  sensitive values were expected on screen there, how many the candidate
  covered, and the ids of any that leaked, any neighbours it clipped, and
  any legible content it obscured, with a clean/defect status.
- **Findings** — one line per defect, typed by failure mode
  (`MISSED`, `PARTIAL`, `WEAK`, `OVER-REDACTED`, `ENCROACHED`,
  `OVER-BLUR`), naming the item and the times. The top findings are also
  copied into reward.json.

The value of this shows on the sibling task: run against the pre-fix
build of that pipeline, the analysis reports exactly the five
single-frame boundary leaks by item and timestamp
(`branch_home#5 … still readable at 82.567s`, `refno#0 … at 118.267s,
123.033s`, and so on) rather than just a lower number.

**Pass bar:** overall ≥ 0.90 AND functional_correctness ≥ 0.95 AND
neighbor_legibility ≥ 0.95.

## Verifier validation (run 2026-09-01, this container)

| candidate | overall | functional | neighbour | constraint | robustness | artifact | verdict |
|---|---|---|---|---|---|---|---|
| oracle output (solution/solve.sh) | **1.0000** | 1.0 | 1.0 | 1.0 | 1.0 (192/192) | 1.0 | pass |
| near-miss A: misses only the tokenized window | 0.9483 | **0.8824** | 1.0 | 1.0 | 0.9688 | 1.0 | **fail** |
| composite "plausible model output" | 0.9149 | **0.8824** | **0.7778** | 0.8889 | 0.9688 | 1.0 | **fail** |
| unmodified original video | 0.4050 | 0.0 | 1.0 | 1.0 | 0.0 | 0.7 | fail |
| cheat: blur the entire frame | 0.6926 | 1.0 | **0.0** | 0.0 | 1.0 | 0.9504 | fail |

The two near-miss rows are the point of the task, and the analysis output
is what makes them useful rather than merely low-scoring:

- **A** covers every value visible on every page, frame-exactly and
  without over-blur, and still fails — on the two instances
  (`cardnum_tok`, `cardname_tok`) that exist only for 21 frames after a
  button press. Its overall (0.948) clears the 0.90 line; the
  functional-correctness floor rejects it, and the findings name the miss
  precisely: *"MISSED — Card Number (tokenized) (cardnum_tok) was never
  redacted; readable across 3 sampled frames at 133.767-134.433s"*.
- The **composite** row is what a plausible model output looks like: it
  misses the tokenized window, over-redacts the Track ID, and oversizes
  several boxes. It fails on three axes at once, and the analysis
  separates them — two `MISSED` findings, two `OVER-REDACTED` findings
  naming Track ID and the URL `trackid=` value, and four `ENCROACHED`
  findings naming the clipped neighbours. That is a failure analysis
  written by the verifier rather than reconstructed by hand.

Both shallow directions are rejected far more bluntly, and their findings
are equally specific: the unmodified original produces a `MISSED` line per
sensitive item, while the blur-everything cheat produces `OVER-REDACTED`
lines naming the billing amount, both captchas, the country dropdown and
the `Help?` link.

The composite row is also the reason neighbour legibility is a separate
pass condition rather than a component folded into a weighted average — a
few stray pixels never move an averaged score enough to matter, but they
are a real defect in a redaction deliverable.

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
