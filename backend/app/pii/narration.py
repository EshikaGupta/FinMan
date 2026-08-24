import re

from .redactor import Redactor


# ------------------------------------------------------------
# Transaction / bank reference identifiers
# ------------------------------------------------------------

REFERENCE_PATTERNS = [

    re.compile(
        r"(?i)"
        r"\b(?:ref|reference|ref\.?\s*no|"
        r"transaction\s*(?:id|no|number)?|"
        r"txn\s*(?:id|no|number)?|"
        r"rrn|utr)\b"
        r"\s*[:#.\-]?\s*"
        r"[A-Za-z0-9\-\/]{6,}"
    ),

]


# ------------------------------------------------------------
# Generic bank/internal reference
#
# Example:
# ICICI001183
# HDFC001234
#
# We only consider a bank-style prefix followed by
# a sufficiently long numeric identifier.
# ------------------------------------------------------------

BANK_REFERENCE_PATTERN = re.compile(
    r"\b"
    r"[A-Z]{4}"
    r"\d{6,}"
    r"\b"
)


def redact_references(
    text,
    redactor,
):
    """
    Redact explicit transaction references and
    bank-internal reference identifiers.

    Merchant names and counterparty names are left
    untouched.
    """

    matches = []

    for pattern in REFERENCE_PATTERNS:

        for match in pattern.finditer(text):

            matches.append(
                (
                    match.start(),
                    match.end(),
                    match.group(),
                )
            )

    for match in BANK_REFERENCE_PATTERN.finditer(
        text
    ):

        matches.append(
            (
                match.start(),
                match.end(),
                match.group(),
            )
        )

    if not matches:
        return text

    # Remove overlapping matches.
    matches.sort(
        key=lambda item: (
            item[0],
            -(item[1] - item[0]),
        )
    )

    filtered = []

    for match in matches:

        if not filtered:
            filtered.append(match)
            continue

        previous = filtered[-1]

        if match[0] >= previous[1]:
            filtered.append(match)

    output = []

    last_position = 0

    for start, end, value in filtered:

        output.append(
            text[last_position:start]
        )

        replacement = redactor.replacement_for(
            "transaction_reference",
            value,
        )

        output.append(
            replacement
        )

        last_position = end

    output.append(
        text[last_position:]
    )

    return "".join(output)


def sanitize_narration(
    text,
):
    """
    Sanitize financial transaction narration.

    Important:
    - merchant names are preserved
    - counterparty names are preserved
    - transaction modes are preserved
    - UPI IDs are redacted
    - email/phone/IFSC/account/card identifiers
      are redacted
    - transaction references are redacted
    """

    if text is None:
        return text

    text = str(text)

    if not text.strip():
        return text

    redactor = Redactor()

    # First remove explicit transaction/bank references.
    text = redact_references(
        text,
        redactor,
    )

    # Then use the existing high-confidence PII
    # detector for:
    #
    # UPI ID
    # email
    # phone
    # PAN
    # Aadhaar
    # IFSC
    # account number
    # card number
    #
    result = redactor.redact(
        text
    )

    return result.text