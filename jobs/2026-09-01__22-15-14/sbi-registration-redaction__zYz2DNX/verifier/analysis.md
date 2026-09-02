# Redaction analysis

## Scores

- `overall`: 0.8355
- `functional_correctness`: 0.9919
- `constraint_satisfaction`: 0.4756
- `neighbor_legibility`: 0.2453
- `robustness`: 0.974
- `artifact_quality`: 1.0

## What counts as PII in this video

| item | what it is | category | page | on screen | samples (hard) |
|---|---|---|---|---|---|
| `acct` | Account Number | account_identifier | registration_form | [[76.567, 90.133]] | 35 (2) |
| `cif` | CIF Number | account_identifier | registration_form | [[76.567, 90.133]] | 35 (2) |
| `branch` | Branch Code | account_identifier | registration_form | [[76.567, 90.133]] | 35 (2) |
| `mobile` | Registered Mobile Number | contact_identifier | registration_form | [[76.567, 90.133]] | 35 (2) |
| `cardnum` | Card Number (PAN) | cardholder_data | payment_gateway | [[131.967, 133.733]] | 6 (2) |
| `expiry` | Card expiry (Valid Thru) | cardholder_data | payment_gateway | [[131.967, 134.433]] | 8 (2) |
| `cardname` | Cardholder's Name | personal_name | payment_gateway | [[131.967, 133.733]] | 6 (2) |
| `cardnum_tok` | Card Number (tokenized) | cardholder_data_derived | payment_gateway | [[133.767, 134.433]] | 3 (3) |
| `cardname_tok` | Cardholder's Name (tokenized) | personal_name_derived | payment_gateway | [[133.767, 134.433]] | 3 (3) |
| `pay_id` | PaymentID (URL) | transaction_identifier | payment_gateway | [[123.267, 134.433]] | 29 (29) |
| `rtr_id` | PaymentID (URL) | transaction_identifier | payment_confirmation | [[134.467, 138.333]] | 11 (11) |
| `c_name` | Cardholder's Name | personal_name | payment_confirmation | [[134.467, 138.333]] | 11 (2) |
| `c_exp` | Card expiry (Expiration Month/Year) | cardholder_data | payment_confirmation | [[134.467, 138.333]] | 11 (2) |
| `tmpuser` | Temporary internet-banking username | credential | create_password | [[138.367, 154.633]] | 42 (2) |
| `kio_pid` | paymentId (URL) | transaction_identifier | create_password | [[138.367, 154.633]] | 42 (42) |
| `kio_auth` | auth code (URL) | transaction_identifier | create_password | [[138.367, 154.633]] | 42 (42) |
| `kio_ref` | ref (URL) | transaction_identifier | create_password | [[138.367, 154.633]] | 42 (42) |

## Deliberately NOT redacted (must stay legible)

| item | what it is | why it is not redacted |
|---|---|---|
| `v_masked_pan` | Card number, site-masked (************ 4567) | the site already masks it; redacting it again destroys demo content for no privacy gain |
| `v_pin_dots` | PIN, shown as dots | already masked by the site |
| `v_captcha_reg` | Captcha challenge image (registration form) | a challenge image, not customer data |
| `v_captcha_pay` | Captcha challenge image (payment page) | a challenge image, not customer data |
| `v_lbl_acct` | 'Account Number' field label | page furniture |
| `v_hint_acct` | Account-number hint text | page furniture |
| `v_lbl_branch` | Branch-code hint text | page furniture |
| `v_prefix91` | '91' country prefix box | a country code, not the subscriber number |
| `v_country` | Country dropdown value ('India') | not identifying |
| `v_amount` | Billing amount (Rs 1.00) | merchant billing info shown by the demo |
| `v_merchant` | Merchant name (STATE BANK GROUP) | merchant billing info shown by the demo |
| `v_help` | 'Help?' link on the expiry row | page furniture |
| `v_url_result` | URL 'result=CAPTURED&auth=' text | parameter names and a non-identifying status value |
| `v_url_post` | URL '&postdate=0715&trackid=' text | parameter names and a date fragment |
| `v_tmpuser_lbl` | 'Temporary Username for Internet Banking is' label | page furniture |
| `v_pay_domain` | Payment gateway scheme/domain/path | tells the viewer which site they are on; not identifying |
| `v_trackid` | Track ID (000072559915072015) | the merchant's own order reference shown in the Billing Information panel alongside Merchant/Website/Amount; it identifies an order, not the customer |
| `v_url_trackid` | URL 'trackid=' value | same merchant order reference as the Track ID field |

## What the candidate did

| item | verdict | coverage | leaked samples | leak times |
|---|---|---|---|---|
| `acct` | partially_redacted | 0.971 | 1/35 | [[76.567, 76.567]] |
| `branch` | partially_redacted | 0.971 | 1/35 | [[76.567, 76.567]] |
| `c_exp` | redacted | 1.0 | 0/11 | - |
| `c_name` | redacted | 1.0 | 0/11 | - |
| `cardname` | redacted | 1.0 | 0/6 | - |
| `cardname_tok` | redacted | 1.0 | 0/3 | - |
| `cardnum` | redacted | 1.0 | 0/6 | - |
| `cardnum_tok` | redacted | 1.0 | 0/3 | - |
| `cif` | partially_redacted | 0.971 | 1/35 | [[76.567, 76.567]] |
| `expiry` | redacted | 1.0 | 0/8 | - |
| `kio_auth` | redacted | 1.0 | 0/42 | - |
| `kio_pid` | redacted | 1.0 | 0/42 | - |
| `kio_ref` | redacted | 1.0 | 0/42 | - |
| `mobile` | partially_redacted | 0.971 | 1/35 | [[76.567, 76.567]] |
| `pay_id` | redacted | 1.0 | 0/29 | - |
| `rtr_id` | redacted | 1.0 | 0/11 | - |
| `tmpuser` | partially_redacted | 0.976 | 1/42 | [[138.367, 138.367]] |

## State timeline

| page | t | PII expected | redacted | leaked | neighbours clipped | legible content obscured | status |
|---|---|---|---|---|---|---|---|
| intro_logo | 0.0–3.8 | 0 | 0 | - | - | - | clean |
| title_card | 3.833–24.333 | 0 | 0 | - | - | - | clean |
| onlinesbi_home | 24.367–34.2 | 0 | 0 | - | - | - | clean |
| login_landing | 34.233–35.867 | 0 | 0 | - | - | - | clean |
| login_page | 35.9–71.633 | 0 | 0 | - | - | - | clean |
| registration_form | 71.667–90.133 | 4 | 0 | acct, branch, cif, mobile | n_acct_hint, n_branch_hint, n_cif_hint, n_mobile_91, n_mobile_hint | v_country, v_hint_acct, v_lbl_branch, v_prefix91 | defect |
| otp_page | 90.167–99.533 | 0 | 0 | - | - | - | clean |
| atm_card_choice | 99.567–123.233 | 0 | 0 | - | - | - | clean |
| payment_gateway | 123.267–134.433 | 6 | 6 | - | n_expiry_help, n_payid_lbl | v_help, v_pay_domain, v_trackid | defect |
| payment_confirmation | 134.467–138.333 | 3 | 3 | - | n_conf_pan, n_conf_pin, n_rtr_right | v_masked_pan, v_pin_dots | defect |
| create_password | 138.367–154.633 | 4 | 3 | tmpuser | n_kio_post, n_kio_ref_lbl, n_kio_result, n_tmpuser_is | v_url_post, v_url_result, v_url_trackid | defect |
| registration_success | 154.667–171.2 | 0 | 0 | - | - | - | clean |
| outro_logo | 171.233–174.833 | 0 | 0 | - | - | - | clean |
| outro_links | 174.867–185.567 | 0 | 0 | - | - | - | clean |

## Findings

- PARTIAL — Account Number (acct) redacted for 34/35 samples; still readable at 76.567s
- PARTIAL — CIF Number (cif) redacted for 34/35 samples; still readable at 76.567s
- PARTIAL — Branch Code (branch) redacted for 34/35 samples; still readable at 76.567s
- PARTIAL — Registered Mobile Number (mobile) redacted for 34/35 samples; still readable at 76.567s
- PARTIAL — Temporary internet-banking username (tmpuser) redacted for 41/42 samples; still readable at 138.367s
- OVER-REDACTED — Country dropdown value ('India') (v_country) must stay legible but no longer matches at 77.567-89.567s
- OVER-REDACTED — 'Help?' link on the expiry row (v_help) must stay legible but no longer matches at 131.967-133.967s
- OVER-REDACTED — Account-number hint text (v_hint_acct) must stay legible but no longer matches at 77.567-89.567s
- OVER-REDACTED — Branch-code hint text (v_lbl_branch) must stay legible but no longer matches at 77.567-89.567s
- OVER-REDACTED — Card number, site-masked (************ 4567) (v_masked_pan) must stay legible but no longer matches at 134.467-137.467s
- OVER-REDACTED — Payment gateway scheme/domain/path (v_pay_domain) must stay legible but no longer matches at 123.267-134.267s
- OVER-REDACTED — PIN, shown as dots (v_pin_dots) must stay legible but no longer matches at 134.467-137.467s
- OVER-REDACTED — '91' country prefix box (v_prefix91) must stay legible but no longer matches at 77.567-89.567s
- OVER-REDACTED — Track ID (000072559915072015) (v_trackid) must stay legible but no longer matches at 134.267s
- OVER-REDACTED — URL '&postdate=0715&trackid=' text (v_url_post) must stay legible but no longer matches at 138.367-154.367s
- OVER-REDACTED — URL 'result=CAPTURED&auth=' text (v_url_result) must stay legible but no longer matches at 138.367-154.367s
- OVER-REDACTED — URL 'trackid=' value (v_url_trackid) must stay legible but no longer matches at 138.367-154.367s
- ENCROACHED — a redaction overlapped its neighbouring text (n_acct_hint) at 77.567-89.567s
- ENCROACHED — a redaction overlapped its neighbouring text (n_branch_hint) at 77.567-89.567s
- ENCROACHED — a redaction overlapped its neighbouring text (n_cif_hint) at 77.567-89.567s
- ENCROACHED — a redaction overlapped its neighbouring text (n_conf_pan) at 134.467-137.467s
- ENCROACHED — a redaction overlapped its neighbouring text (n_conf_pin) at 134.467-137.467s
- ENCROACHED — a redaction overlapped its neighbouring text (n_expiry_help) at 131.967-133.967s
- ENCROACHED — a redaction overlapped its neighbouring text (n_kio_post) at 138.367-154.367s
- ENCROACHED — a redaction overlapped its neighbouring text (n_kio_ref_lbl) at 138.367-154.367s
- ENCROACHED — a redaction overlapped its neighbouring text (n_kio_result) at 138.367-154.367s
- ENCROACHED — a redaction overlapped its neighbouring text (n_mobile_91) at 77.567-89.567s
- ENCROACHED — a redaction overlapped its neighbouring text (n_mobile_hint) at 77.567-89.567s
- ENCROACHED — a redaction overlapped its neighbouring text (n_payid_lbl) at 123.267-134.267s
- ENCROACHED — a redaction overlapped its neighbouring text (n_rtr_right) at 134.467-137.467s
- ENCROACHED — a redaction overlapped its neighbouring text (n_tmpuser_is) at 139.367-154.367s
- OVER-BLUR — off-target changed pixels exceeded the frame budget on 18 sampled frames at 121.0-155.0s
