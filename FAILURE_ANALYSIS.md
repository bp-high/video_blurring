# Target model failure analysis

Two independent runs of **Claude Opus 4.7** through the Claude Code harness
on `collinear-candidate/sbi-registration-redaction`. Both failed, and they
failed the same way, which is the useful part: the failure is a property of
the task rather than an accident of one run.

| | Run A | Run B |
| --- | --- | --- |
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
| technique | solid black `drawbox` | Gaussian `gblur` overlays |

Pass bars are `overall >= 0.90`, `functional_correctness >= 0.95` and
`neighbor_legibility >= 0.95`. Both runs clear none of them on overall, and
both are an order of magnitude short on neighbour legibility.

Neither run came close to using its budget. The agent timeout is 3 hours
and the oracle needs 6 to 8 minutes of compute, so no part of either
failure is caused by time pressure.

Detection was not the problem. Run A found essentially every sensitive
value (functional correctness 0.992, robustness 0.974), including the URL
query identifiers and the 21 frame tokenized card window that the task is
built around. The failures are about precision and discipline, not
perception.

---

## Failure 1: region-level hypothesis

Both agents decided what shape the answer takes before starting, and both
picked the wrong shape. Instead of covering each piece of private data,
they covered whole areas of the page.

Think of redacting a paper form. The right move is to black out the four
filled in fields. What both runs did was drop one large rectangle over the
entire right hand column. That hides the four values, and also hides the
country dropdown, the hint text beside each field, and the small `91`
prefix box.

Both runs used **five rectangles to handle seventeen separate items**.

Run A's boxes, and the must-stay-legible probes each one destroyed:

| box | size | oversize | probes destroyed |
| --- | --- | --- | --- |
| registration form | 160x105 | 2.9x | `v_country` `v_hint_acct` `v_lbl_branch` `v_prefix91` |
| URL bar | 780x15 | 2.6x | `v_pay_domain` `v_url_post` `v_url_result` `v_url_trackid` |
| payment gateway | 155x100 | 2.1x | `v_help` `v_pin_dots` |
| confirmation page | 160x55 | 6.7x | `v_masked_pan` `v_pin_dots` `v_trackid` |
| temporary username | 65x16 | 1.7x | none |

Run B's geometry is different in detail and identical in kind: 140x102,
825x26, 175x130, 175x58, 62x20. The URL bar box is 825 pixels wide, which
is nearly the full frame width. It hides five identifiers that must be
hidden and four things that must stay readable, in one stroke.

Two independent runs, different tooling, the same framing of the problem.

## Failure 2: timing-only iteration

Both agents revised their work several times. Run A re-encoded the video
four times, Run B three times. That looks like careful iteration.

Every revision changed only **when** a blur switched on and off. The box
positions and sizes never moved. Run A's coordinates are identical across
all four attempts:

```
form:    76.2-96.0  ->  76.2-91.5  ->  76.7-90.3  ->  76.7-90.3
gateway:    -135.5  ->     -135.5  ->     -135.5  ->     -135.0
confirm:    -139.5  ->     -139.5  ->     -139.5  ->     -138.5
```

So the agent held one hypothesis about what could be wrong, which was "my
timing is slightly off", and polished that one thing across three cycles.
It never asked whether the boxes were the right size, even though box size
was costing it roughly half of constraint satisfaction.

Run B did adjust one box, and adjusted it the wrong way. At the step
labelled "re-render with wider stronger URL bar blur" it widened the URL
region from 800x20 to 825x26. It had already destroyed four probes in that
bar; its corrective action was to cover more.

## Failure 3: self-verification with the wrong acceptance criterion

Both agents checked their own output, and both checked the right frames.
Run A extracted 27 frames from its own video and inspected every one,
including the frame showing the black rectangle across the registration
form and the frames showing the blacked out address bar. Run B sampled its
whole output at 2 frames per second.

This is not skipped verification. They looked directly at the damage and
approved it.

The problem is the question they asked. Both were checking "is the private
data hidden?", got yes, and stopped. Neither asked "did I cover anything I
was supposed to leave alone?". That second question is worth 45 percent of
the score and was never put.

Both runs also confirmed `cv2` was importable and then never used it. Every
check was visual inspection of JPEGs. With no OCR in the image, they had
OpenCV and NumPy available and performed no pixel measurement of their own
work.

## Failure 4: blur strength, and an instructive inversion

Run B chose per region blur strengths of sigma 10, 9, 10, 8, and **5** for
the temporary username, which is the smallest text on screen. Measured
directly on the graded frame:

```
tmpuser rect 46x13 at t=146.367        NCC      covered (< 0.60)
original                              0.993          no
Run A  (solid black fill)             0.448         YES
Run B  (gblur sigma=5)                0.674          no
```

Run B missed the coverage threshold by 0.074 and scored **0.0 across all 42
samples**, a total miss on a value Run A covered cleanly. The region looks
blurred to a human eye, which is exactly why visual inspection passed it.

This is the "too gentle" end of the valid band. On this footage the band is
roughly Gaussian sigma >= 3 or pixelation blocks >= 6px; below that, the
value stays matchable and the change also falls under the minimum
defacement floor.

Run B's other misses cluster on a single seam. Its gateway box ends at
`t=134` and its confirmation box begins there, but the tokenized card
window runs 133.77 to 134.43. Hence `cardnum_tok` and `cardname_tok` at
1/3 and `expiry` at 6/8. One boundary chosen on a round number rather than
on the content.

## Failure 5: report hallucination

Both final reports contradict the agent's own actions.

**Run A** listed the site-masked card number and the PIN dots under what it
covered, saying it covered them "for consistency", and then listed the same
two items under "Left as-is (already safe)".

**Run B** does the same thing more subtly. Its table admits blurring them
("***4567 mask and PIN dots were already masked but blurred anyway"), then
its "Left visible" list claims "PIN field (rendered as `****` on both entry
and confirmation)" and "Card number on confirmation page (`****4567`)". It
also lists "Country" as data it blurred and separately as something left
visible.

Run B closes with: "Verified by re-sampling frames at 2 fps from
`/app/output/redacted.mp4` across the entire timeline; nothing readable
remains in the target regions." The temporary username was readable in all
42 sampled frames. A check was run, the check could not detect that class
of failure, and the result was reported as though it could.

Note what this is not. Both agents read the rule about already-masked
values, quoted it correctly, and overrode it deliberately. That is a
judgement failure rather than a comprehension failure, which is the more
interesting kind.

---

## Fairness note

The instruction delivered to both runs is 825 characters and names only one
exclusion: values the site has already masked, illustrated by the starred
card number and the PIN dots.

Of the 12 damaged legibility probes in Run A, **2 are squarely the agent's
fault** (`v_masked_pan`, `v_pin_dots`) and its own report proves it
understood and overrode the rule. The other 10 (`v_country`,
`v_hint_acct`, `v_lbl_branch`, `v_help`, `v_prefix91`, `v_pay_domain`,
`v_trackid`, `v_url_result`, `v_url_post`, `v_url_trackid`) have no basis
in the delivered text. Run B is the same picture.

The sharpest case is the address bar. The verifier requires `pay_id`,
`rtr_id`, `kio_pid`, `kio_auth` and `kio_ref` to be hidden while
`result=`, `postdate=`, `trackid=` and the scheme, domain and path stay
readable, all in the same bar at the same moment. Nothing in the
instruction says the address bar is in scope at all.

So the headline `neighbor_legibility 0.245` currently overstates the
agent's culpability. The findings that stand entirely on their own merits,
and that should lead any writeup, are:

1. Run B's blur too weak to cover the temporary username, a complete miss
   on 42 samples, reported as verified.
2. Both runs' boundary errors at the `t=134` page transition.
3. Knowingly blurring the one exclusion the instruction did state.
4. Final reports that contradict the actions they describe.

Restoring two sentences to the instruction, one saying that non customer
content such as labels, hints, links and the merchant reference must come
through untouched, and one saying each blur should be kept to the value it
covers, would make all 12 attributable and turn this into clean evidence.

---

## Reproducing

```bash
harbor run -p ./collinear-candidate/sbi-registration-redaction \
    -a claude-code -m anthropic/claude-opus-4-7
harbor view ./jobs
```

Per run, the evidence lives at `jobs/<job>/<trial>/`:

| path | what it holds |
| --- | --- |
| `verifier/reward.json` | the six scores |
| `verifier/analysis.md` | PII inventory, page state timeline, typed findings |
| `verifier/analysis.json` | the same, plus per item coverage numbers |
| `artifacts/redacted.mp4` | the video the agent produced |
| `agent/trajectory.json` | steps, timing, token and cost totals |
| `agent/sessions/projects/-app/*.jsonl` | full tool calls, and the frames the agent viewed, base64 encoded |

The frames an agent inspected are not written to disk, since `/app/work` is
not a collected artifact. They can be recovered from the session log; the
set recovered from Run A is committed under `agent_run_frames/`.
