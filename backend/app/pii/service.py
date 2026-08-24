from .detector import detect_pii
from .redactor import Redactor


class PIISecurityError(Exception):
    """
    Raised when sensitive information remains
    after the redaction step.
    """

    pass


class PIIService:

    def __init__(self):

        self.redactor = Redactor()

    def sanitize(self, text):

        if not text:
            return text

        result = self.redactor.redact(
            text
        )

        remaining = detect_pii(
            result.text
        )

        if remaining:

            raise PIISecurityError(
                "PII remains after redaction."
            )

        return result