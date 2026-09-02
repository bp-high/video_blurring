# Agent run frames — recovered from the trajectory

Every frame Claude Opus 4.7 looked at during trial
`sbi-registration-redaction__zYz2DNX` (job `2026-09-01__22-15-14`,
overall 0.8355).

The agent wrote these to `/app/work/` inside the container, which is not a
collected artifact, so the files themselves went away with the container.
They survive only because each image was passed back to the model and
recorded as base64 in the trial's session log:

    jobs/2026-09-01__22-15-14/sbi-registration-redaction__zYz2DNX/
      agent/sessions/projects/-app/307df7b9-8e43-457a-afa8-4bbc1490a5c1.jsonl

All 95 were decoded from that log and renamed after their container paths.

## `self_verification/` (27 frames)

Frames of the agent's **own output**, extracted by the agent to check its
work. This is the evidence it had in front of it when it declared the job
done. `v_*` are from its first encode, `v2_`/`v3_`/`v4_` from the three
re-encodes that followed; the number is the timestamp in seconds.

Notable: `v_80.jpg` (one black box across five form rows, hint text sliced
mid-word), `v_122.jpg` and `v_145.jpg` (the entire URL bar blacked out),
`v3_134.jpg` (confirmation page with the site-masked card number and PIN
dots destroyed). The agent viewed each of these and accepted them — the
over-redaction was inspected, not overlooked.

## `input_inspection/` (68 frames)

Frames of the **seed** video the agent sampled while surveying the
recording: `frames_1fps__*` is the full-timeline sweep at 1 fps, and the
`frames_<a>_<b>__*` sets are denser samples (5 or 10 fps) around the
registration form, the payment gateway and the redirect pages.

## Reproducing

`agent/sessions/.../*.jsonl` holds one JSON object per line. Image bytes
live under `message.content[].content[].source.data` on `tool_result`
entries, matched to their filename via the `tool_use_id` of the
corresponding `Read` call.
