#!/bin/bash
# Oracle solution: this recording navigates between static pages, so the
# work is (a) knowing every place a sensitive value is rendered — including
# the tokenized card values the gateway substitutes after Submit, and the
# transaction identifiers in the URL bar — and (b) turning each into a
# frame-exact interval.
#
# detect_static.py matches each declared value inside a small window around
# its known position on EVERY frame of the page that shows it, which yields
# exact appearance/disappearance frames; blur.py then renders those
# intervals and muxes the original audio.
#
# Runtime: ~6-8 minutes.
set -eu
ASSETS="$(cd "$(dirname "$0")/assets" && pwd)"
cd /app
mkdir -p output work

python3 "$ASSETS/detect_static.py" \
  --video input/sbi_registration.mp4 \
  --templates "$ASSETS/templates" \
  --spec "$ASSETS/items.json" \
  --out work/intervals.json \
  --report work/report.json

python3 "$ASSETS/blur.py" \
  --video input/sbi_registration.mp4 \
  --hits "$ASSETS/empty_hits.json" \
  --extra work/intervals.json \
  --out output/redacted.mp4 \
  --ffmpeg ffmpeg
