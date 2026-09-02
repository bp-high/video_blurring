# Redact the SBI internet-banking registration recording

`/app/input/sbi_registration.mp4` is a 3m06s, 852x478@30fps screen
recording (with narration) of SBI's public "online registration for
internet banking" walkthrough: a customer opens onlinesbi.com, fills in
the registration form, receives an OTP, pays a ₹1 verification charge
with a debit card, and sets a login password.

Unlike a staged demo, this one was recorded against a real account, so
real customer data sits on screen for much of it. Watch the whole thing,
find every place that data shows up, and blur it so it can't be read
back. Save the result to `/app/output/redacted.mp4`

## What to leave alone

If the site has already masked something for you a card number printed
with most of its digits starred out, a PIN shown as dots it is safe as
it stands.
