"""
Comprehensive Test Suite for Feature 2: PII Detection and Protection
Tests detection across all supported categories, algorithmic validation (Luhn, Verhoeff),
redaction policies, false-positive protection on financial terminology, and log sanitization.
"""

from app.services.pii_detector import pii_service, PIIDetectorService
from app.core.config import settings
from fastapi.testclient import TestClient
from app.main import app
import logging
import io

client = TestClient(app)


def test_email_detection_and_redaction():
    """Verify email address detection and redaction."""
    text = "Please send the Q3 report to CFO at john.doe@investcorp.com immediately."
    res = pii_service.inspect(text, policy="REDACT")
    assert res.has_pii is True
    assert "EMAIL" in res.categories_detected
    assert "john.doe@investcorp.com" not in res.sanitized_text
    assert "[EMAIL_REDACTED]" in res.sanitized_text

    # Mask policy
    res_mask = pii_service.inspect(text, policy="MASK")
    assert "john.doe@investcorp.com" not in res_mask.sanitized_text
    assert "@investcorp.com" in res_mask.sanitized_text


def test_phone_number_detection():
    """Verify US and Indian phone number detection."""
    queries = [
        ("Contact IR desk at +1-800-555-0199 for filings", "PHONE_NUMBER"),
        ("Call manager directly on +91 9876543210 regarding the margin call", "PHONE_NUMBER"),
    ]
    for q, expected_cat in queries:
        res = pii_service.inspect(q)
        assert res.has_pii is True, f"Failed to detect phone in: {q}"
        assert expected_cat in res.categories_detected
        assert "[PHONE_NUMBER_REDACTED]" in res.sanitized_text


def test_payment_card_luhn_algorithm():
    """Verify payment cards are validated with Luhn algorithm and non-cards are rejected."""
    # Valid Visa card passing Luhn: 4532 0150 1234 5671
    valid_card = "4532 0150 1234 5671"
    assert PIIDetectorService.luhn_checksum(valid_card) is True

    text_with_card = f"Charged the terminal fee to corporate card {valid_card}."
    res = pii_service.inspect(text_with_card)
    assert res.has_pii is True
    assert "PAYMENT_CARD" in res.categories_detected
    assert valid_card not in res.sanitized_text

    # Invalid Luhn number (e.g. order tracking number) should NOT be flagged as card
    invalid_card = "4532 0150 1234 5678"
    assert PIIDetectorService.luhn_checksum(invalid_card) is False
    text_invalid = f"Order tracking ID 4532015012345678 processed."
    res_invalid = pii_service.inspect(text_invalid)
    assert "PAYMENT_CARD" not in res_invalid.categories_detected


def test_us_ssn_detection():
    """Verify US Social Security Number detection and redaction."""
    text = "The primary account holder SSN on record is 123-45-6789."
    res = pii_service.inspect(text)
    assert res.has_pii is True
    assert "SSN" in res.categories_detected
    assert "123-45-6789" not in res.sanitized_text
    assert "[SSN_REDACTED]" in res.sanitized_text


def test_indian_pan_detection():
    """Verify Indian PAN card detection."""
    text = "Tax deduction under Section 194C for PAN ABCDE1234F recorded."
    res = pii_service.inspect(text)
    assert res.has_pii is True
    assert "PAN" in res.categories_detected
    assert "ABCDE1234F" not in res.sanitized_text
    assert "[PAN_REDACTED]" in res.sanitized_text


def test_indian_aadhaar_verhoeff_algorithm():
    """Verify Indian Aadhaar detection with Verhoeff checksum validation."""
    # Aadhaar with valid Verhoeff: e.g. 2183 9201 8472 -> check if verhoeff returns boolean
    # Let's test Verhoeff algorithm directly:
    # 2345 6789 0123 -> calculate or test known valid Verhoeff number
    # If 999999999999 fails Verhoeff:
    assert PIIDetectorService.verhoeff_checksum("012345678901") is False  # Cannot start with 0
    assert PIIDetectorService.verhoeff_checksum("112345678901") is False  # Cannot start with 1

    # Find or verify a valid 12-digit Aadhaar number
    # Let's compute a valid 12-digit number for test:
    # Digits: 2000 0000 000 + check digit
    base = "20000000000"
    from app.services.pii_detector import VERHOEFF_D, VERHOEFF_P
    c = 0
    for i, item in enumerate(reversed(base)):
        c = VERHOEFF_D[c][VERHOEFF_P[(i + 1) % 8][int(item)]]
    inv_table = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]
    check_digit = inv_table[c]
    valid_aadhaar = f"{base}{check_digit}"
    assert PIIDetectorService.verhoeff_checksum(valid_aadhaar) is True

    text = f"Customer provided Aadhaar number {valid_aadhaar[:4]} {valid_aadhaar[4:8]} {valid_aadhaar[8:]} for KYC."
    res = pii_service.inspect(text)
    assert res.has_pii is True
    assert "AADHAAR" in res.categories_detected
    assert valid_aadhaar not in res.sanitized_text


def test_bank_account_and_ifsc():
    """Verify bank account numbers and IFSC code detection."""
    text = "Transfer dividends to A/C: 987654321098 at branch IFSC HDFC0001234."
    res = pii_service.inspect(text)
    assert res.has_pii is True
    assert "BANK_ACCOUNT" in res.categories_detected
    assert "987654321098" not in res.sanitized_text


def test_financial_queries_no_false_positives():
    """Ensure legitimate financial research figures, ratios, and tickers are NOT flagged as PII."""
    safe_queries = [
        "What is EBITDA and how is it calculated for capital-intensive firms?",
        "Compare HDFC Bank and ICICI Bank's Net Interest Margin (NIM) of 3.4% and 4.2%.",
        "Apple generated $94.93 billion in revenue, with iPhone sales of $46.22B and EPS of $1.64.",
        "The Reserve Bank of India kept the repo rate unchanged at 6.50% and SDF at 6.25%.",
        "Reliance Industries announced an annual capital expenditure of 1,20,000 crore rupees.",
        "Berkshire Hathaway holds $276.9 billion in cash equivalents and short-term US Treasury bills.",
        "TSMC gross margin forecast is 53.5% with wafer prices rising 8% in 2025.",
    ]

    for q in safe_queries:
        res = pii_service.inspect(q)
        assert res.has_pii is False, f"False positive detected in query: '{q}', categories: {res.categories_detected}"
        assert res.sanitized_text == q


def test_pii_logging_sanitizer():
    """Verify that logger with PIISanitizingFilter automatically purges sensitive PII from output."""
    log_stream = io.StringIO()
    test_logger = logging.getLogger("pii_test_logger")
    test_logger.setLevel(logging.INFO)
    
    from app.core.logging import PIISanitizingFilter
    handler = logging.StreamHandler(log_stream)
    handler.addFilter(PIISanitizingFilter())
    handler.setFormatter(logging.Formatter("%(message)s"))
    test_logger.addHandler(handler)

    test_logger.info("User query from client: my email is secret.cfo@hedgefund.com and tel is +1 800 555 0199")
    log_output = log_stream.getvalue()

    assert "secret.cfo@hedgefund.com" not in log_output
    assert "+1 800 555 0199" not in log_output
    assert "[EMAIL_REDACTED]" in log_output or "[PHONE_NUMBER_REDACTED]" in log_output


def test_api_pii_inspect_endpoint():
    """Verify the /api/pii/inspect endpoint works for client pre-flight checks."""
    response = client.post(
        "/api/pii/inspect",
        json={"text": "Review filings for analyst.sarah@vanguard.com with SSN 123-45-6789"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_pii"] is True
    assert "EMAIL" in data["categories"]
    assert "SSN" in data["categories"]
    assert "123-45-6789" not in data["sanitized_text"]


def test_api_research_blocking_policy():
    """Verify that when PII_POLICY is BLOCK, queries with sensitive PII return 400 Bad Request."""
    # Temporarily set policy to BLOCK
    original_policy = settings.PII_POLICY
    try:
        settings.PII_POLICY = "BLOCK"
        response = client.post(
            "/api/research",
            json={"query": "Investigate transaction on card 4532 0150 1234 5671"}
        )
        assert response.status_code == 400
        error_detail = response.json().get("detail", {})
        assert error_detail.get("error") == "PII_DETECTED"
        assert "PAYMENT_CARD" in error_detail.get("categories", [])
    finally:
        settings.PII_POLICY = original_policy


if __name__ == "__main__":
    tests = [
        test_email_detection_and_redaction,
        test_phone_number_detection,
        test_payment_card_luhn_algorithm,
        test_us_ssn_detection,
        test_indian_pan_detection,
        test_indian_aadhaar_verhoeff_algorithm,
        test_bank_account_and_ifsc,
        test_financial_queries_no_false_positives,
        test_pii_logging_sanitizer,
        test_api_pii_inspect_endpoint,
        test_api_research_blocking_policy,
    ]
    passed = 0
    for t in tests:
        print(f"Running {t.__name__}...", end=" ")
        try:
            t()
            print("PASSED")
            passed += 1
        except Exception as e:
            print(f"FAILED: {e}")
            raise
    print(f"\nAll {passed}/{len(tests)} tests passed successfully!")
