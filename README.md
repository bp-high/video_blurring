# Video blurring — SBI netbanking recordings

Redacts sensitive on-screen information in SBI internet-banking screen
recordings, and packages each one as a verifiable long-horizon **Harbor
task** (seed video, programmatic verifier with per-occurrence coverage /
visibility / blur-size measures, oracle solution, run report).

| video | redacted output | Harbor task |
| --- | --- | --- |
| Transfer of Savings Account demo (2m13s) | [`output/sbi_transfer_demo_blurred.mp4`](output/sbi_transfer_demo_blurred.mp4) | [`collinear-candidate/sbi-netbanking-redaction/`](collinear-candidate/sbi-netbanking-redaction) |
| Internet-banking registration walkthrough (3m06s) | [`output/sbi_registration_redacted.mp4`](output/sbi_registration_redacted.mp4) | [`collinear-candidate/sbi-registration-redaction/`](collinear-candidate/sbi-registration-redaction) |

Both tasks share one programmatic verifier. Besides scoring, it writes an
`analysis.md` / `analysis.json` per run: an inventory of what counts as
PII in that video (with category and rationale) and what deliberately does
not, a page-by-page **state timeline** of which values were expected on
screen and what the candidate did with each, and one finding per defect
typed by failure mode (`MISSED`, `PARTIAL`, `WEAK`, `OVER-REDACTED`,
`ENCROACHED`, `OVER-BLUR`) — so a model run can be analysed without
re-watching the video.

The two recordings need different machinery, which is why they make two
distinct tasks. The transfer demo **pans, scrolls and changes browser
zoom**, so its pipeline tracks each string across scales
(`detect.py` + `blur.py`). The registration walkthrough navigates between
**static pages** but shows *live, unmasked* data — including card values
the payment gateway silently replaces with hashed tokens mid-page — so its
pipeline declares each value's position and asks, per frame, whether it is
on screen (`detect_static.py` + `blur.py`).

---

## Transfer of Savings Account demo

Redacts sensitive on-screen information in the SBI "RINB – Transfer of
Savings Account" netbanking demo screen recording (854x480, 2m13s).

The blurred video is committed at
[`output/sbi_transfer_demo_blurred.mp4`](output/sbi_transfer_demo_blurred.mp4).

## What gets blurred

| Item | Where it appears |
| --- | --- |
| Home branch name and branch code | account summary, transfer form, confirmation, success, history screens |
| Destination branch name and branch code (typed and displayed) | transfer form, confirmation, success, history screens |
| Transfer reference number and its history-table row (incl. date) | history screen |

Fields the demo itself already masks — the username (`xxxxxxxx`), the
password dots, the welcome name (`Mr. XXXX...`) and the account number
(`000000XXXXXXXX602`) — are left as-is: they carry no real information and
blurring them only added noise.

## How it works

The recording pans, scrolls and changes browser zoom between screens, so
static blur boxes don't work. Instead ([`blur_pipeline/`](blur_pipeline)):

1. **`detect.py`** — multi-scale template matching (OpenCV, normalized
   cross-correlation at 17 scales, 0.70–1.78x). Small PNG crops of each
   sensitive string are matched in two passes: a 1 fps sweep to find when
   each string is on screen, then a 10 fps sweep inside those windows
   recording every occurrence (position, size, score) to `hits.json`.
   "Slim" top-half template variants catch rows partially clipped by the
   caption bar at the frame edge during scroll transitions.
2. **`blur.py`** — turns hits into blur events with spatial padding and
   temporal padding (blur starts before a string appears and ends after it
   leaves), bridges match gaps at a stable location (e.g. when the mouse
   cursor parks on the text and breaks the match), pixelates +
   Gaussian-blurs each region per frame, and pipes the frames to ffmpeg
   (libx264, original audio copied). `--filters` applies per-template
   time/region/score constraints (see `sbi_demo_filters.json`),
   `--extra` adds manual blur events, and `--clamp-end` stops all blur at
   the hard cut to the outro.
3. **`verify.py`** — re-runs every template against the *output* video at
   10 fps over the full scale range; any match at the detection threshold
   means a string survived redaction. The final output verifies clean.

## Reproducing

The source video and the template crops are intentionally **not** committed —
they contain the very content being redacted. With the source video and a
`templates/` directory of crops:

```bash
pip install opencv-python-headless numpy
python3 blur_pipeline/detect.py --video input.mp4 --templates templates/ \
    --out hits.json --tmin 28 --tmax 125 --thresh 0.70
python3 blur_pipeline/blur.py   --video input.mp4 --hits hits.json \
    --filters sbi_demo_filters.json --extra sbi_demo_extra.json \
    --clamp-end 123.03 --out blurred.mp4
python3 blur_pipeline/verify.py --video blurred.mp4 --templates templates/ --thresh 0.70
```

---

## Internet-banking registration walkthrough

The redacted video is committed at
[`output/sbi_registration_redacted.mp4`](output/sbi_registration_redacted.mp4).

### What gets redacted

| Item | Where it appears |
| --- | --- |
| Account number, CIF number, branch code, registered mobile number | User Driven Registration form |
| Card number, cardholder's name, card expiry | payment gateway |
| The hashed/tokenized card number and cardholder name the gateway substitutes in-place after Submit | payment gateway, during "Processing… Please wait" |
| Card expiry month/year and cardholder's name | payment confirmation page |
| Temporary internet-banking username | create-password page |
| Transaction identifiers in URL query strings (payment id, `auth`, `ref`) | payment and post-payment redirect pages |

Left legible on purpose: the site's own masked card number
(`************ 4567`) and PIN dots, both captcha images, the readable
parts of URLs (scheme, domain, path, `result=CAPTURED`, `postdate=…`,
`trackid=…`), all labels, hints, merchant and amount — and the **Track
ID**, which is the merchant's own order reference shown beside Merchant /
Website / Amount: it identifies an order, not the customer, so redacting
it counts as over-redaction.

### How it works

The pages here don't move, so the hard part is knowing *what* to cover and
*exactly when* — including content that changes while a page stays up:

1. **`detect_static.py`** — each value is declared once in
   [`sbi_reg_items.json`](sbi_reg_items.json) with its template crop, the
   page's frame window, and where it sits. The detector matches it in a
   small window around that position on **every** frame, giving frame-exact
   appearance/disappearance times (a form filled in one spliced frame, a
   field re-rendered as a hash after Submit). Every item matched at
   score 1.00 with zero position drift, confirming the pages are static.
2. **`blur.py`** — renders those intervals (reused from the demo pipeline;
   detection output is passed as `--extra`, with an empty `--hits`).

```bash
python3 blur_pipeline/detect_static.py --video input.mp4 \
    --templates templates/ --spec sbi_reg_items.json \
    --out intervals.json --report report.json
echo '[]' > empty_hits.json
python3 blur_pipeline/blur.py --video input.mp4 --hits empty_hits.json \
    --extra intervals.json --out redacted.mp4
```
