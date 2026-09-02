# SBI internet-banking registration redaction — Harbor task

A net-new, long-horizon Harbor task in which an agent must irreversibly
obscure live customer data in a 3m06s screen recording of SBI's public
"online registration for internet banking" walkthrough — **without**
damaging the parts of the page that have to stay legible.

Task directory: [`collinear-candidate/sbi-registration-redaction/`](collinear-candidate/sbi-registration-redaction)

Unlike a staged demo, this recording was made against a real account, so it shows unmasked account, card and transaction data. 

An agent has to inventory what is sensitive across 14 page states, derive exact intervals for each, render them tightly enough not to clip the surrounding page, and verify its own output.

## Running it

```bash
# oracle solution must score 1.0
harbor run -p ./collinear-candidate/sbi-registration-redaction -a oracle

# a target model
harbor run -p ./collinear-candidate/sbi-registration-redaction \
    -a claude-code -m anthropic/claude-opus-4-7

# browse trajectories and scores
harbor view ./jobs
```


## Layout

| path | what it is |
| --- | --- |
| [`instruction.md`](collinear-candidate/sbi-registration-redaction/instruction.md) | task prompt and constraints given to the agent |
| [`task.toml`](collinear-candidate/sbi-registration-redaction/task.toml) | metadata, timeouts, resources, network policy, oracle, artifacts |
| [`environment/Dockerfile`](collinear-candidate/sbi-registration-redaction/environment/Dockerfile) | pinned image (opencv-python-headless 5.0.0.93, numpy 2.4.6, imageio-ffmpeg 0.6.0) |
| [`environment/seed/input/`](collinear-candidate/sbi-registration-redaction/environment/seed) | the seed recording, copied to `/app/input/` at build |
| [`tests/test.sh`](collinear-candidate/sbi-registration-redaction/tests/test.sh) | verifier entrypoint; writes `/logs/verifier/reward.json` + `reward.txt` |
| [`tests/grade.py`](collinear-candidate/sbi-registration-redaction/tests/grade.py) | the grader — programmatic, no LLM judging |
| [`tests/_analysis.py`](collinear-candidate/sbi-registration-redaction/tests/_analysis.py) | turns grader counters into `analysis.md` / `analysis.json` |
| [`tests/ground_truth.json`](collinear-candidate/sbi-registration-redaction/tests/ground_truth.json) | 17 redact / 18 visible / 18 neighbour items with per-sample rects |
| [`tests/fixtures/`](collinear-candidate/sbi-registration-redaction/tests/fixtures) | template crops the grader matches against |
| [`solution/solve.sh`](collinear-candidate/sbi-registration-redaction/solution/solve.sh) | oracle; scores 1.0 on every axis |
| [`RUN_REPORT.md`](collinear-candidate/sbi-registration-redaction/RUN_REPORT.md) | task idea, fairness rationale, verifier design, model runs, limitations |
| [`golden_redacted/`](golden_redacted) | the oracle's output video, for reference |
| [`agent_run_frames/`](agent_run_frames) | frames recovered from a model run's trajectory |

## Verifier

`tests/grade.py` reads the seed video, the candidate video and
`ground_truth.json` in one lockstep pass and writes `reward.json`:

| metric | what it measures |
| --- | --- |
| `functional_correctness` | every sensitive value is unrecognisable in place (NCC < 0.60) |
| `constraint_satisfaction` | must-stay-legible probes survive, neighbours untouched, off-target pixels within budget |
| `neighbor_legibility` | text adjoining each redaction is pixel-untouched — reported separately so a run can be rejected on it |
| `robustness` | coverage restricted to samples tagged hard (transitions, tokenized window) |
| `artifact_quality` | resolution / frame count / audio preserved, blur neither too weak nor oversized |

`overall = 0.40·functional + 0.30·constraint + 0.15·robustness + 0.15·artifact`

Every measure has an opposing one, so blurring everything and blurring
nothing both score badly. Alongside the reward it writes `analysis.md` and
`analysis.json`: a PII inventory, a page-by-page state timeline, and one
finding per defect typed by failure mode (`MISSED`, `PARTIAL`, `WEAK`,
`OVER-REDACTED`, `ENCROACHED`, `OVER-BLUR`) so a run can be analysed
without re-watching the video.


## Provenance

The seed is SBI's own public YouTube walkthrough. Everything else item
declarations, ground truth, fixtures (crops of the seed itself), grader,
and the oracle pipeline was written from scratch for this task.
