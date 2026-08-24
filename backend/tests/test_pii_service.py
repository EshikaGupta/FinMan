from app.pii.service import PIIService,PIISecurityError
from app.pii.detector import detect_pii
import pytest

def test_security_gate_blocks_remaining_pii():

    service = PIIService()

    # Replace the redactor temporarily with
    # one that does nothing.
    class BrokenRedactor:

        def redact(self, text):

            class Result:
                pass

            result = Result()
            result.text = text
            result.matches = []

            return result

    service.redactor = BrokenRedactor()

    text = (
        "Account Number: "
        "123456789012"
    )

    with pytest.raises(
        PIISecurityError
    ):

        service.sanitize(text)
def test_sanitize_removes_pii():

    service = PIIService()

    text = (
        "Account Number: 123456789012\n"
        "PAN: ABCDE1234F\n"
        "Email: eshika@example.com"
    )

    result = service.sanitize(
        text
    )

    assert (
        "123456789012"
        not in result.text
    )

    assert (
        "ABCDE1234F"
        not in result.text
    )

    assert (
        "eshika@example.com"
        not in result.text
    )

def test_sanitized_text_contains_no_pii():

    service = PIIService()

    text = (
        "Account Number: 123456789012\n"
        "UPI: eshika@okhdfcbank\n"
        "IFSC: HDFC0001234"
    )

    result = service.sanitize(
        text
    )

    remaining = detect_pii(
        result.text
    )

    assert remaining == []

def test_empty_text():

    service = PIIService()

    result = service.sanitize("")

    assert result == ""

def test_none_text():

    service = PIIService()

    result = service.sanitize(None)

    assert result is None