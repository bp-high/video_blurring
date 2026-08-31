#!/bin/bash
# Oracle solution: multi-scale template-matching detection over the video,
# then per-track blur scheduling with occlusion gap-bridging, page-swap
# clamping, hand-measured bands for the caption-clipped zoom transition,
# and pixelate+Gaussian redaction muxed with the original audio.
#
# Runtime: ~35-45 minutes, dominated by the detection sweep (17 scales,
# 10 fps sampling inside active windows).
set -eu
ASSETS="$(cd "$(dirname "$0")/assets" && pwd)"
cd /app
mkdir -p output work

python3 "$ASSETS/detect.py" \
  --video input/sbi_demo.mp4 \
  --templates "$ASSETS/templates" \
  --out work/hits.json \
  --tmin 28 --tmax 125 --thresh 0.70

python3 "$ASSETS/blur.py" \
  --video input/sbi_demo.mp4 \
  --hits work/hits.json \
  --filters "$ASSETS/sbi_demo_filters.json" \
  --extra "$ASSETS/sbi_demo_extra.json" \
  --cuts "$ASSETS/sbi_demo_cuts.json" \
  --clamp-end 123.03 \
  --out output/redacted.mp4 \
  --ffmpeg ffmpeg
