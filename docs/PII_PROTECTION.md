# Irium PII Detection and Protection Specification

## Overview
Irium implements algorithmic Personally Identifiable Information (PII) detection, redaction, and policy enforcement to safeguard user privacy across research workflows, LLM calls, document uploads, and application logs.

---

## Supported PII Categories & Validation Algorithms

| PII Category | Identifier Pattern | Validation Method | Example Masked Output |
| :--- | :--- | :--- | :--- |
| **Payment Cards** | Visa, Mastercard, Amex, Discover, RuPay (13–19 digits) | **Luhn Checksum Algorithm** (ISO/IEC 7812) | `[CARD_REDACTED: ****-****-****-5671]` |
| **Indian Aadhaar** | 12-digit UID (`XXXX XXXX XXXX`) | **Verhoeff Checksum Algorithm** (UIDAI specification) | `[AADHAAR_REDACTED: XXXX-XXXX-8472]` |
| **Indian PAN** | 10-char alphanumeric (`[A-Z]{5}[0-9]{4}[A-Z]`) | Entity type validation (P/C/H/F/A/T/B/L/J/G) | `[PAN_REDACTED: ABXXXXX4F]` |
| **US SSN** | 9 digits (`XXX-XX-XXXX`) | Format & Area/Group validity checks | `[SSN_REDACTED: XXX-XX-XXXX]` |
| **Email Addresses** | RFC 5322 standard emails | Domain structure validation & TLD length check | `[EMAIL_REDACTED: j***e@investcorp.com]` |
| **Phone Numbers** | US `(XXX) XXX-XXXX`, Indian `+91 9XXXX XXXXX`, International | Regex with boundary & length validation | `[PHONE_REDACTED]` |
| **Bank Accounts & IFSC** | Contextual account numbers (9–18 digits), Indian IFSC, IBAN | Mod-97 checksum for IBAN; RBI pattern for IFSC | `[BANK_ACCOUNT_REDACTED: ****0123]` |

---

## Handling Policies

Configurable via `PII_POLICY` in `.env`:

1. **`REDACT` (Default)**: Replaces detected PII with contextual category tags (e.g., `[EMAIL_REDACTED]`, `[CARD_REDACTED]`). Safe queries proceed to LLMs and agents without compromising sensitive data.
2. **`BLOCK`**: Rejects incoming requests containing sensitive PII with HTTP 400 Bad Request, returning descriptive instructions to remove PII.
3. **`MASK`**: Partially obscures the value preserving non-sensitive audit digits (e.g. last 4 card digits).
4. **`LOG_ONLY`**: Logs detection warnings while leaving text unchanged (development mode).

---

## Log Sanitization Guarantee

A custom `PIISanitizingFilter` is attached to Python's root application logger. Any string passed to `logger.info`, `logger.warning`, or `logger.error` is scrubbed of detected PII *before* output to stdout or file sinks, preventing unintentional credential leakage.

---

## False Positive Mitigations in Financial Research

Financial research queries routinely contain large numbers, currency signs, ratios, and percentages (e.g., *"$94.9 billion revenue"*, *"repo rate of 6.50%"*, *"loan book of 1,20,000 crore"*).

To prevent false positives:
- **Currency Prefixes**: Numbers immediately preceded by `$`, `€`, `₹`, `Rs`, `INR`, `USD` are exempted from phone number detection.
- **Financial Suffixes**: Numbers followed by `B`, `M`, `cr`, `crore`, `lakh`, `%`, `bps` are excluded.
- **Algorithmic Verification**: Payment cards and Aadhaar numbers are only flagged if they satisfy strict mathematical checksums (Luhn and Verhoeff). Ordinary serial numbers and tracking numbers that fail checksums are rejected.

---

## Known Limitations and Potential False Negatives/Positives

1. **Checksum Collision**: A random 16-digit number has a ~10% probability of passing the Luhn checksum by chance.
2. **Unlabelled Bank Account Numbers**: Bank account numbers without explicit contextual keywords (like *"A/C"*, *"Account"*, *"IBAN"*) cannot be detected without risking high false-positive rates against general corporate figures.
3. **Regional Identifiers**: Identifiers specific to regions outside the US, India, and the EU (such as UK National Insurance or Canadian SIN) require explicit rule extensions.
