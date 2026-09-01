# Redact the SBI internet-banking registration recording

`/app/input/sbi_registration.mp4` is a 3m06s, 852x478@30fps screen
recording (with narration) of SBI's public "online registration for
internet banking" walkthrough: a customer opens onlinesbi.com, fills the
User Driven Registration form, receives an OTP, pays a ₹1 verification
charge with a debit card on the payment gateway, and sets a login
password.

Unlike a staged demo, this recording shows **live, unmasked account
data**. Produce `/app/output/redacted.mp4`: the same video with every
occurrence of that data irreversibly obscured (blur, pixelation, or solid
fill — your choice), and nothing else damaged.

## What must be obscured — every frame it is on screen

On the registration form:

1. Account Number, 2. CIF Number, 3. Branch Code, 4. Registered Mobile
   Number (the number itself; the `91` country-prefix box is not the
   number).

On the payment gateway and its confirmation page:

5. Card Number, 6. Cardholder's Name, 7. Card expiry (Valid Thru month
   and year, and the Expiration Month / Expiration Year rows on the
   confirmation page), 8. Track ID.

On the create-password page:

9. The Temporary Username issued for internet banking.

Anywhere they appear in the browser's address bar:

10. Transaction identifiers in URL query strings — the payment id, and the
    `auth`, `ref` and `trackid` values on the post-payment redirect URL.

**Inspect the whole timeline, not a sample of it.** Values here appear and
disappear on a single frame, and at least one field's *content changes*
while the page stays up — what is rendered in a field is not always what
you saw when the page loaded. A value readable for even one frame is a
leak.

## What must NOT be touched

- Values the site itself already masks: the confirmation page's masked
  card number (`************ 4567`) and the PIN dots. They carry no
  recoverable data — leave them legible.
- The captcha challenge images on the registration form and the payment
  page.
- The non-identifying parts of URLs: scheme, domain, path, and the
  `result=CAPTURED` and `postdate=…` parameters.
- All other page content: field labels, hint text in parentheses, the
  billing merchant and amount, buttons, links, and the browser chrome.
  Redaction must not appear on a page before its sensitive value does, or
  linger after the page changes.

## Quality bars (measured by the verifier)

- Container: same resolution and frame rate, frame count within ±10,
  audio track preserved (duration within ±0.6 s).
- Coverage: at each sampled occurrence, the value must no longer be
  recognisable in place (normalized cross-correlation against the original
  patch < 0.60).
- Legibility: every must-not-touch item above must still match its
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
- The deliverable is the video at `/app/output/redacted.mp4`. Intermediate
  files may go under `/app/work/`.
- Verify your own output before finishing. The failure modes that matter
  are occurrences you never found, occurrences that survive for a few
  frames at a page change, and collateral blur on content that must stay
  legible.
