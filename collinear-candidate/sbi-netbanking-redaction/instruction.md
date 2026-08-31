# Redact the SBI netbanking demo video

`/app/input/sbi_demo.mp4` is a 2m13s, 854x480@30fps screen recording (with
narration audio) of SBI's public 2017 internet-banking demo: a user logs
in, opens e-Services → "Transfer of Savings Account", submits a branch
transfer, and checks the transfer history. The recording pans, scrolls and
changes browser zoom between screens.

Produce `/app/output/redacted.mp4`: the same video with the sensitive
account details irreversibly obscured (blur, pixelation, or solid fill —
your choice), and nothing else damaged.

## What must be obscured — every visible occurrence, at every zoom level

1. The home branch name `SANYOGITAGANJ,INDORE` (account summary table,
   transfer form, confirmation, success and history screens).
2. The home branch code `30013` (confirmation, success, history screens).
3. The destination branch code `04388` — both as typed into the "Branch
   Code" form input and as displayed on the confirmation, success and
   history screens.
4. The destination branch name `PBB, SAPNA SANGEETA` — both in the "Branch
   Name" form input (partially visible while typing) and on the
   confirmation, success and history screens.
5. The transfer reference number (`ATB…4921`) on the History tab, together
   with the rest of its table row (old/new branch codes and transfer date).

"Every visible occurrence" includes the hard cases: while a page is
mid-zoom or mid-scroll, while a row is partially clipped by the burned-in
caption bar at the bottom edge, and while the mouse cursor sits on top of
the text. An occurrence readable for even a few frames counts as a leak.

## What must NOT be touched

- Fields the demo already masks: the username (`xxxxxxxx`), the password
  dots, the welcome name (`Mr. XXXX…`), and the account number
  (`000000XXXXXXXX602`). They carry no real information — leave them
  legible.
- All other page content: headings, menus, sidebar items, buttons, the
  caption bar, the browser chrome. Blur must not linger on a page after a
  page change, and must not appear on a page before the sensitive content
  does.

## Quality bars (measured by the verifier)

- Container: same resolution and frame rate, frame count within ±10,
  audio track preserved (duration within ±0.6 s).
- Coverage: at each sampled occurrence, the sensitive string must no
  longer be recognisable in place (normalized cross-correlation against
  the original text patch < 0.60).
- Legibility: the must-not-touch items above must still match their
  original appearance in place (NCC ≥ 0.80).
- Minimal footprint: at any sampled time, changed pixels outside the
  (dilated) sensitive regions must be under 2% of the frame; per frame,
  total changed area must stay within 12x the active sensitive area.
- Real obscuring: a covered region must actually be defaced (changed
  pixels ≥ 12% of the text box), not merely perturbed enough to break
  matching.

A run passes when `overall ≥ 0.90` and `functional_correctness ≥ 0.95`
in the verifier's reward.json.

## Notes

- `ffmpeg` (statically bundled), OpenCV (`cv2`) and NumPy are installed.
  No network access is available or needed.
- The deliverable is the video file at `/app/output/redacted.mp4`. You are
  free to create any intermediate files under `/app/work/`.
- Verify your own output before finishing: the failure modes that matter
  are occurrences you never found, occurrences that reappear for a moment
  during transitions or cursor overlap, and collateral blur on content
  that must stay legible.
