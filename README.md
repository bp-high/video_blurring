# Video blurring — SBI netbanking demo

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
