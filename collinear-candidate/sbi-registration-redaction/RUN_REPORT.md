# RUN_REPORT: Blur PII info in banking demo videos

  

## Task idea

  

Blurring PII info in demo videos has been reported as a nightmare [# Blurring sensitive info in videos-- Nightmare job?](https://www.reddit.com/r/UTEST/comments/1f1lpg3/blurring_sensitive_info_in_videos_nightmare_job/)
This recording of SBI's public internet-banking registration walkthrough shows

**live, unmasked** customer data like account number, CIF, mobile, a debit card with cardholder name and expiry, a bank-issued temporary username, and transaction identifiers that are spread across seven pages of a 3m06s video session. 

Finding and covering all of it requires an agent to inventory a whole timeline rather than a handful of sampled screens, and to notice that the page does not always show what it showed a second ago.

  

Two properties make it long-horizon:

  

1. The screens/ information keeps changing and the agent has to judge by looking at the page across its whole lifetime.

2. **Values appear and vanish on a single frame.** The recording is spliced: the registration form is empty at frame 2296 and fully populated at 2297; the card form likewise at 3958/3959. Redaction has to be frame-exact in both directions, a pipeline that samples at 1 or 10 fps and pads its intervals either leaks a frame or paints blur onto an empty form.

Add to that identifiers hidden in URL query strings (easy to overlook entirely) and a set of values that must be *left alone* which are the site's own
masked card number, the PIN dots and the captchas rewards inspection discipline over pattern-matching.

The task is not brittle: any redaction mechanism and any detection approach passes, provided the measured outcomes hold.

## Long Horizon

**the three subgoals**

**1. Build the inventory.** Work out what actually counts as sensitive across 3 minutes 6 seconds and 14 distinct page states. This is not a lookup. Nothing in the container tells the agent what to look for: the image copies only the seed video into `/app`, and `tests/` is mounted by the harness after the agent has finished. The ground truth, the fixtures and the oracle are never visible. The information exists only in 5568 frames, so the agent has to sample and inspect the video itself. Some items are only findable by looking carefully, like the transaction identifiers sitting in the browser address bar.

**2. Pin down when each value is on screen.** The recording is spliced, so values appear and vanish on a single frame. The form is empty at frame 2296 and fully filled at frame 2297. Sampling at 1 fps and padding the result either leaks the first frame or paints blur over an empty form, and both are penalised. Getting this right means testing presence per frame, not per second.

**3. Render inside a tight constraint.** Each interval has to be covered firmly enough to destroy the text, and no wider than the value itself. Labels, hint text and neighbouring columns sit a few pixels away. The container has to come out with the same resolution, frame count and audio.

**Hypothesis formation and verification** are threaded through all three. The agent has to form a theory about what a page contains, test it against frames, and revise. Then it has to re-scan its own output, because every failure mode here is invisible unless you go looking. 

## Verifier design (tests/grade.py fully programmatic)

  

Ground truth (`tests/ground_truth.json`) holds 17 sensitive instances with

396 (time, rect, scale) samples of which 192 tagged *hard* (the tokenized-card window, every interval's first and last frame, and the URL identifiers) plus 209 must-stay-visible samples across 18 probes (site-masked card number, PIN dots, both captchas, field labels, hint text, merchant and
amount, the Track ID and its URL counterpart, the `Help?` link, the readable parts of URLs, the payment-gateway domain) and 192 neighbour
samples across 18 probes. 

It also carries the recording's 14 page segments, which the analysis uses as its state timeline. Every sample was validated against the original video: sensitive samples match there at NCC ≥ 0.75, visibility and neighbour probes at ≥ 0.82. Zero samples were dropped in validation.

  

### What counts as PII here

  

The task draws an explicit line, and the verifier scores both sides of it.

**Sensitive** (redact): account number, CIF, branch code and registered mobile; card number, cardholder name and expiry, the bank-issued temporary username and the payment/`auth`/`ref` identifiers in URL query strings.

**Not sensitive** (must stay legible): values the site already masks

(`************ 4567`, the PIN dots), the captchas, page labels and hints, merchant and amount, the readable parts of URLs, Captchas.

  

### Reward:
- `functional_correctness` (0.40): per-instance fraction of samples where the value no longer matches in place (NCC < 0.60, ±8 px).

- `constraint_satisfaction` (0.30): 0.4 visibility (probes still match at NCC ≥ 0.80) + 0.3 neighbour legibility + 0.3 over-blur budget (changed pixels outside dilated sensitive rects ≤ 2% of the frame, on a 2 s grid).

- `neighbor_legibility` (reported separately, and a pass condition): 20 probes on the text abutting a redaction the label left of each field, the hint or URL parameter right of it, the rows above and below on the confirmation page, the browser's search icon beside the last URL parameter. Each must be left **pixel-untouched**: the check is changed pixels (unsmoothed, threshold 20, tolerance 2% of the probe rect)
Being pixel-based it also localises the fault, the
failing probe names the neighbour that was clipped.

- `robustness` (0.15): coverage restricted to the 192 hard samples.

- `artifact_quality` (0.15): container integrity (resolution, frame count, audio) + blur-size bounds a covered rect must be genuinely defaced (changed pixels ≥ 12% of the text box) and per-frame changed area must stay ≤ 12x the active sensitive area.

Original and candidate are decoded in one lockstep pass, so frames are index-aligned and there is no seek nondeterminism.

**Why this verifier is not brittle**

The verifier measures pixels and whether each sensitive value still shows up where it used to, and how much of the rest of the page changed.

It does not care how you redact. Black, white, grey, blur and pixelation all score the same, because frames are compared in grayscale and only the size of the change counts.

**It tolerates normal variation** an 8 pixel search margin for drift, brightness normalization, noise smoothing, and range checks on frame count and duration. 

The metrics pull against each other, so shortcuts fail. Blurring everything scores 0.693, doing nothing scores 0.405, and the oracle scores 1.0 with 192 of 192 hard samples covered. Grading is deterministic and offline.

### State tracking and failure analysis
Alongside the reward the verifier writes `analysis.json` and `analysis.md`, so a model run can be analysed without re-watching the video:

- **PII inventory** — every sensitive item with its plain-English label, category (`account_identifier`, `cardholder_data`, `cardholder_data_derived`, `personal_name`, `credential`, `transaction_identifier`, …), the page it belongs to, why it is sensitive, and the exact intervals it is on screen. Paired with a **not-PII** table giving, for each thing that must stay legible, the reason it is not redacted.

- **State timeline** — one row per page of the recording: how many sensitive values were expected on screen there, how many the candidate covered, and the ids of any that leaked, any neighbours it clipped, and any legible content it obscured, with a clean/defect status.

- **Findings** — one line per defect, typed by failure mode (`MISSED`, `PARTIAL`, `WEAK`, `OVER-REDACTED`, `ENCROACHED`, `OVER-BLUR`), naming the item and the times. 

 
**Pass bar:** overall ≥ 0.95 AND functional_correctness ≥ 0.95 AND neighbor_legibility ≥ 0.95.

## Oracle solution
`solution/solve.sh`: `detect_static.py` matches each declared value inside a small window around its known position on **every frame** of the page that shows it, producing frame-exact appearance/disappearance
intervals; `blur.py` renders those intervals with pixelate+Gaussian redaction and muxes the original audio unchanged. The tokenized card
values are declared as their own items, so their intervals are found the same way as everything else  and the oracle's discovery of them is recorded
in `assets/items.json`, not hardcoded into the renderer.

Note the shape of the oracle: for a recording of static pages the hard part is *knowing what to look for and when*, so the pipeline is a declarative item list plus a frame-exact presence detector.
  

## Reproduction
```

harbor run -p ./collinear-candidate/sbi-registration-redaction -a oracle

harbor run -p ./collinear-candidate/sbi-registration-redaction -a <agent> -m <gpt-5.5-high-or-opus-4.7>

harbor view ./jobs

```

## Claude-Opus 4.7 + Claude-Code harness run results
Both failed, and they failed the same way, which is the useful part.



| Run A | Run B | |
| -- | -- | -- |
| job | `2026-09-01__22-15-14` | `2026-09-02__03-18-30` | 
| trial | `sbi-registration-redaction__zYz2DNX` | `sbi-registration-redaction__rfFLqt8` |
| **overall** | **0.8355** | **0.7752** |
| functional_correctness | 0.9919 | 0.8460 |
| constraint_satisfaction | 0.4756 | 0.4767 |
| neighbor_legibility | 0.2453 | 0.2301 |
| robustness | 0.9740 (187/192) | 0.9583 (184/192) |
| artifact_quality | 1.000 | 1.000 |
| wall clock | 8m 45s | 13m 55s |
| steps / tool calls | 45 / 130 | 62 / 135 |
| cost | $3.01 | $4.44 |
| blur technique | solid black `drawbox` | Gaussian `gblur` overlays |

 ### Failure 1: region-level hypothesis
Both agents decided what shape the answer takes before starting, and both picked the wrong shape. Instead of covering each piece of private data, they covered whole areas of the page.

eg. Run A 
![alt text](image.png)

eg. Run B

![alt text](image-2.png)

### Failure 2: timing-only iteration

Both agents revised their work several times. Run A re-encoded the video four times, Run B three times. That looks like careful iteration.

Every revision changed only **when** a blur switched on and off. The box positions and sizes never moved. Run A's coordinates are identical across
all four attempts:

```
form:    76.2-96.0  ->  76.2-91.5  ->  76.7-90.3  ->  76.7-90.3
gateway:    -135.5  ->     -135.5  ->     -135.5  ->     -135.0
confirm:    -139.5  ->     -139.5  ->     -139.5  ->     -138.5
```

So the agent held one hypothesis about what could be wrong, which was "my timing is slightly off", and polished that one thing across three cycles.
It never asked whether the boxes were the right size, even though box size was costing it roughly half of constraint satisfaction.

Run B did adjust one box, and adjusted it the wrong way. At the step labelled "re-render with wider stronger URL bar blur" it widened the URL
region from 800x20 to 825x26. It had already destroyed four probes in that bar and its corrective action was to cover more.

### Failure 3: self-verification with the wrong acceptance criterion

Both agents checked their own output, and both checked the right frames.
Run A extracted 27 frames from its own video and inspected every one,
including the frame showing the black rectangle across the registration
form and the frames showing the blacked out address bar. Run B sampled its
whole output at 2 frames per second.

 They looked directly at the damage and
approved it.

The problem is the question they asked. Both were checking "is the private
data hidden?", got yes, and stopped. Neither asked "did I cover anything I
was supposed to not cover or by mistake covered the neighbourhood objects/fields?". 

Every check was visual inspection of JPEGs. They had
OpenCV and NumPy available and performed no pixel measurement of their own work.

### Failure 4: Hallucination in reasoning
Both final reports contradict the agent's own actions.

**Run A** listed the site-masked card number and the PIN dots under what it
covered, saying it covered them "for consistency", and then listed the same
two items under "Left as-is (already safe)".
![alt text](image-3.png)
**Run B** does the same thing more subtly. Its table admits blurring them
("***4567 mask and PIN dots were already masked but blurred anyway"), then
its "Left visible" list claims "PIN field (rendered as `****` on both entry
and confirmation)" and "Card number on confirmation page (`****4567`)". It
also lists "Country" as data it blurred and separately as something left
visible.
![alt text](image-4.png) 




## Provenance and licensing

  

- Seed video: SBI(State Bank of India's) own public YouTube walkthrough for online internet-banking registration. Used as a realistic redaction subject.

- Everything else like the item declarations, ground truth, fixtures , grader, and the `detect_static.py` oracle was created from scratch for this task. 
- The redacted output of this task is published in this repository at

`golden_redacted/sbi_registration_redacted.mp4`.

  

## Limitations
- Ground truth is tied to this exact encode and re-encoding the seed would require regenerating fixtures and ground truth.
