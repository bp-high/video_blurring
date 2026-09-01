#!/bin/bash
# Verifier entrypoint. Grades /app/output/redacted.mp4 against the seed
# video and the ground truth, writing /logs/verifier/reward.json and
# reward.txt. All checks are programmatic (template matching + pixel-diff
# measures); no LLM judging.
set -u
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /logs/verifier

python3 "$TESTS_DIR/grade.py" \
  --original /app/input/sbi_registration.mp4 \
  --candidate /app/output/redacted.mp4 \
  --ground-truth "$TESTS_DIR/ground_truth.json" \
  --fixtures "$TESTS_DIR/fixtures" \
  --out-dir /logs/verifier \
  --ffmpeg ffmpeg

if [ ! -f /logs/verifier/reward.json ]; then
  echo '{"overall": 0.0, "functional_correctness": 0.0, "constraint_satisfaction": 0.0, "robustness": 0.0, "artifact_quality": 0.0, "error": "grader crashed"}' > /logs/verifier/reward.json
  echo "0.0" > /logs/verifier/reward.txt
fi
