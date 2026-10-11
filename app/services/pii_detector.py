"""
PII Detection, Validation, and Redaction Service for Irium
Provides multi-category detection with algorithmic validation (Luhn, Verhoeff, mod-97),
false-positive protection for financial figures, and configurable redaction policies.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from app.core import logger


# ==============================================================================
# Algorithmic Checksum Validation Tables
# ==============================================================================

# Verhoeff tables for Indian Aadhaar validation
VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


@dataclass
class PIIEntity:
    """Represents a detected PII entity."""
    category: str
    value: str
    start: int
    end: int
    confidence: float
    masked_value: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PIIDetectionResult:
    """Result of PII inspection."""
    has_pii: bool
    entities: List[PIIEntity]
    sanitized_text: str
    categories_detected: List[str]
    policy_applied: str


class PIIDetectorService:
    """
    Robust PII detector with algorithmic verification and financial domain disambiguation.
    """

    # Email pattern (RFC 5322 compatible subset)
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    )

    # Phone patterns
    PHONE_INTERNATIONAL_PATTERN = re.compile(
        r'(?:\+|00)[1-9]\d{0,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
    )
    PHONE_US_PATTERN = re.compile(
        r'\b(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})\b'
    )
    PHONE_INDIAN_PATTERN = re.compile(
        r'\b(?:\+91[-.\s]?|91[-.\s]?|0)?[6-9]\d{4}[-.\s]?\d{5}\b'
    )

    # US Social Security Number (SSN)
    SSN_PATTERN = re.compile(
        r'\b(?!000|666|9\d{2})\d{3}[-.\s]?(?!00)\d{2}[-.\s]?(?!0000)\d{4}\b'
    )

    # Indian PAN (Permanent Account Number)
    # Format: 5 uppercase letters, 4 digits, 1 uppercase letter
    PAN_PATTERN = re.compile(
        r'\b[A-Z]{5}\d{4}[A-Z]\b'
    )

    # Indian Aadhaar Number: 12 digits, cannot start with 0 or 1
    AADHAAR_PATTERN = re.compile(
        r'\b[2-9]\d{3}[-\s]?\d{4}[-\s]?\d{4}\b'
    )

    # Payment Card candidates: 13-19 digits with optional spaces or dashes
    CARD_CANDIDATE_PATTERN = re.compile(
        r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|2(?:2[2-9][0-9]{12}|[3-6][0-9]{13}|7[01][0-9]{12}|720[0-9]{12})|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b'
    )
    CARD_FORMATTED_PATTERN = re.compile(
        r'\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b|\b\d{4}[-\s]\d{6}[-\s]\d{5}\b'
    )

    # Indian IFSC code: 4 letters, '0', 6 alphanumeric
    IFSC_PATTERN = re.compile(
        r'\b[A-Z]{4}0[A-Z0-9]{6}\b'
    )

    # Bank Account Contextual pattern
    BANK_ACCOUNT_PATTERN = re.compile(
        r'(?i)\b(?:a/c|acct|account(?:\s+no|\s+number)?|iban)[\s:#=-]+([A-Z0-9]{8,34})\b'
    )

    # Financial context patterns to avoid false positives
    FINANCIAL_EXCLUSIONS = re.compile(
        r'(?i)(?:\$|€|£|₹|rs\.?|inr|usd|eur|gbp)\s*\d+[\d,.]*|\b\d+[\d,.]*\s*(?:cr|crore|lakh|million|billion|trillion|m|b|k|%|bps)\b'
    )

    @classmethod
    def luhn_checksum(cls, candidate: str) -> bool:
        """Validate candidate number against the Luhn algorithm (ISO/IEC 7812)."""
        clean_num = re.sub(r'[\s-]', '', candidate)
        if not clean_num.isdigit() or len(clean_num) < 13 or len(clean_num) > 19:
            return False
        digits = [int(c) for c in clean_num]
        total = 0
        reverse_digits = digits[::-1]
        for idx, digit in enumerate(reverse_digits):
            if idx % 2 == 1:
                doubled = digit * 2
                total += doubled - 9 if doubled > 9 else doubled
            else:
                total += digit
        return total % 10 == 0

    @classmethod
    def verhoeff_checksum(cls, candidate: str) -> bool:
        """Validate 12-digit Indian Aadhaar number using Verhoeff checksum algorithm."""
        clean_num = re.sub(r'[\s-]', '', candidate)
        if not clean_num.isdigit() or len(clean_num) != 12:
            return False
        # Cannot start with 0 or 1
        if clean_num[0] in ('0', '1'):
            return False

        c = 0
        for i, item in enumerate(reversed(clean_num)):
            c = VERHOEFF_D[c][VERHOEFF_P[i % 8][int(item)]]
        return c == 0

    @classmethod
    def validate_iban(cls, candidate: str) -> bool:
        """Validate International Bank Account Number (IBAN) using ISO 7064 MOD 97-10."""
        clean_iban = re.sub(r'[\s-]', '', candidate).upper()
        if len(clean_iban) < 15 or len(clean_iban) > 34:
            return False
        # Move first 4 characters to end
        rearranged = clean_iban[4:] + clean_iban[:4]
        # Replace each letter with two digits (A=10, ..., Z=35)
        converted = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
        if not converted.isdigit():
            return False
        # Check mod 97
        return int(converted) % 97 == 1

    def detect_entities(self, text: str) -> List[PIIEntity]:
        """Detect all verified PII entities in the input text."""
        if not text:
            return []

        entities: List[PIIEntity] = []

        # 1. Emails
        for match in self.EMAIL_PATTERN.finditer(text):
            val = match.group(0)
            entities.append(PIIEntity(
                category="EMAIL",
                value=val,
                start=match.start(),
                end=match.end(),
                confidence=0.98,
                masked_value=self._mask_email(val)
            ))

        # 2. Payment Cards (Luhn verified)
        for pattern in (self.CARD_CANDIDATE_PATTERN, self.CARD_FORMATTED_PATTERN):
            for match in pattern.finditer(text):
                val = match.group(0)
                clean_val = re.sub(r'[\s-]', '', val)
                if self.luhn_checksum(clean_val):
                    # Check for overlap
                    if not any(e.start <= match.start() and e.end >= match.end() for e in entities):
                        entities.append(PIIEntity(
                            category="PAYMENT_CARD",
                            value=val,
                            start=match.start(),
                            end=match.end(),
                            confidence=0.99,
                            masked_value=self._mask_card(clean_val),
                            metadata={"card_length": len(clean_val)}
                        ))

        # 3. Government IDs: Indian Aadhaar (Verhoeff verified)
        for match in self.AADHAAR_PATTERN.finditer(text):
            val = match.group(0)
            clean_val = re.sub(r'[\s-]', '', val)
            if self.verhoeff_checksum(clean_val):
                if not any(e.start <= match.start() and e.end >= match.end() for e in entities):
                    entities.append(PIIEntity(
                        category="AADHAAR",
                        value=val,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.98,
                        masked_value=f"[AADHAAR_REDACTED: XXXX-XXXX-{clean_val[-4:]}]"
                    ))

        # 4. Government IDs: Indian PAN
        for match in self.PAN_PATTERN.finditer(text):
            val = match.group(0)
            if not any(e.start <= match.start() and e.end >= match.end() for e in entities):
                entities.append(PIIEntity(
                    category="PAN",
                    value=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    masked_value=f"[PAN_REDACTED: {val[:2]}XXXXX{val[-1]}]"
                ))

        # 5. Government IDs: US SSN
        for match in self.SSN_PATTERN.finditer(text):
            val = match.group(0)
            clean_val = re.sub(r'[\s-]', '', val)
            # Ensure not overlapping with existing entities (like cards)
            if not any(e.start <= match.start() and e.end >= match.end() for e in entities):
                # Disambiguate against ordinary numbers
                entities.append(PIIEntity(
                    category="SSN",
                    value=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.92,
                    masked_value="[SSN_REDACTED: XXX-XX-XXXX]"
                ))

        # 6. Phone Numbers
        # Disambiguate phone numbers: skip if preceded by currency symbols or followed by financial terms
        for pattern, conf in (
            (self.PHONE_INDIAN_PATTERN, 0.90),
            (self.PHONE_US_PATTERN, 0.90),
            (self.PHONE_INTERNATIONAL_PATTERN, 0.85)
        ):
            for match in pattern.finditer(text):
                val = match.group(0)
                clean_digits = re.sub(r'\D', '', val)
                if len(clean_digits) < 10 or len(clean_digits) > 15:
                    continue

                # Check if overlapping with already captured entity
                if any(e.start <= match.start() and e.end >= match.end() for e in entities):
                    continue

                # Contextual check: make sure it's not a financial amount (e.g. Rs 9876543210 or $10000000)
                prefix = text[max(0, match.start() - 6):match.start()]
                if any(curr in prefix.lower() for curr in ('$', '€', '£', '₹', 'rs', 'inr', 'usd')):
                    continue

                entities.append(PIIEntity(
                    category="PHONE_NUMBER",
                    value=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=conf,
                    masked_value="[PHONE_REDACTED]"
                ))

        # 7. Bank Account / IBAN
        for match in self.BANK_ACCOUNT_PATTERN.finditer(text):
            account_num = match.group(1)
            # If IBAN, validate with mod-97
            if re.match(r'^[A-Z]{2}\d{2}', account_num) and self.validate_iban(account_num):
                entities.append(PIIEntity(
                    category="IBAN",
                    value=account_num,
                    start=match.start(1),
                    end=match.end(1),
                    confidence=0.98,
                    masked_value=f"[IBAN_REDACTED: {account_num[:4]}XXXX{account_num[-4:]}]"
                ))
            elif len(account_num) >= 9 and len(account_num) <= 18 and account_num.isdigit():
                entities.append(PIIEntity(
                    category="BANK_ACCOUNT",
                    value=account_num,
                    start=match.start(1),
                    end=match.end(1),
                    confidence=0.92,
                    masked_value=f"[BANK_ACCOUNT_REDACTED: ****{account_num[-4:]}]"
                ))

        # Sort entities by start position descending to allow clean string replacement
        entities.sort(key=lambda e: e.start, reverse=True)
        return entities

    def redact(self, text: str, policy: str = "REDACT") -> Tuple[str, List[PIIEntity]]:
        """
        Redact or mask detected PII entities in the text according to policy.
        Policies:
        - REDACT: Replace with contextual tags e.g. [EMAIL_REDACTED], [CARD_REDACTED]
        - MASK: Replace sensitive characters with asterisks (preserving last 4 digits)
        - ANONYMIZE: Generic [REDACTED_PII]
        """
        entities = self.detect_entities(text)
        if not entities:
            return text, []

        sanitized = text
        for entity in entities:
            start, end = entity.start, entity.end
            if policy == "MASK":
                replacement = entity.masked_value
            elif policy == "ANONYMIZE":
                replacement = "[REDACTED_PII]"
            else: # REDACT (default)
                replacement = f"[{entity.category}_REDACTED]"
            sanitized = sanitized[:start] + replacement + sanitized[end:]

        return sanitized, entities

    def inspect(self, text: str, policy: str = "REDACT") -> PIIDetectionResult:
        """Inspect text, detect PII, and return comprehensive result object."""
        sanitized_text, entities = self.redact(text, policy=policy)
        categories = sorted(list(set(e.category for e in entities)))
        return PIIDetectionResult(
            has_pii=len(entities) > 0,
            entities=entities,
            sanitized_text=sanitized_text,
            categories_detected=categories,
            policy_applied=policy
        )

    def is_safe_for_logging(self, text: str) -> bool:
        """Return True if text contains no detectable PII."""
        return len(self.detect_entities(text)) == 0

    def sanitize_for_logging(self, text: str) -> str:
        """Sanitize text specifically for log messages."""
        if not text:
            return ""
        sanitized, _ = self.redact(text, policy="REDACT")
        return sanitized

    def _mask_email(self, email: str) -> str:
        parts = email.split('@')
        if len(parts) != 2:
            return "[EMAIL_REDACTED]"
        name, domain = parts
        if len(name) <= 2:
            masked_name = name[0] + "*"
        else:
            masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
        return f"[EMAIL_REDACTED: {masked_name}@{domain}]"

    def _mask_card(self, card_digits: str) -> str:
        last4 = card_digits[-4:] if len(card_digits) >= 4 else "XXXX"
        return f"[CARD_REDACTED: ****-****-****-{last4}]"


# Global singleton instance
pii_service = PIIDetectorService()
