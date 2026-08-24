import re

from .models import PIIMatch


# ============================================================
# High-confidence identifiers
# ============================================================

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+91[\s-]?)?"
    r"[6-9]\d{9}"
    r"(?!\d)"
)


PAN_PATTERN = re.compile(
    r"\b[A-Z]{5}\d{4}[A-Z]\b",
    re.IGNORECASE,
)


AADHAAR_PATTERN = re.compile(
    r"(?<!\d)"
    r"\d{4}[\s-]\d{4}[\s-]\d{4}"
    r"(?!\d)"
)


IFSC_PATTERN = re.compile(
    r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    re.IGNORECASE,
)


UPI_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"[A-Za-z0-9][A-Za-z0-9._-]*"
    r"@"
    r"[A-Za-z0-9][A-Za-z0-9-]*"
    r"(?![A-Za-z0-9])"
)



# ============================================================
# Context-dependent financial identifiers
# ============================================================

ACCOUNT_NUMBER_PATTERN = re.compile(
    r"(?i)"
    r"(?:"
        r"account"
        r"(?:\s+number|\s+no\.?|\s*#)?"
        r"|a/c"
        r"|acct\.?"
        r"|bank\s+a/c"
        r"|savings\s+a/c"
        r"|current\s+a/c"
        r"|sb\s+a/c"
    r")"
    r"\s*[:#.\-]?\s*"
    r"([0-9](?:[0-9\s\-]*[0-9])?)"
)


CARD_NUMBER_PATTERN = re.compile(
    r"(?i)"
    r"(card"
    r"(?:\s+number|\s+no\.?|\s*#)?"
    r"|debit\s+card"
    r"|credit\s+card)"
    r"\s*[:#.\-]?\s*"
    r"((?:\d[ -]?){13,19})"
)


CUSTOMER_ID_PATTERN = re.compile(
    r"(?i)"
    r"(?:"
        r"customer"
        r"(?:\s+id|\s+number|\s+no\.?)"
        r"|cust\.?"
        r"(?:\s+id|\s+no\.?)"
    r")"
    r"\s*[:#.\-]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9\-]{4,30})"
)

MASKED_ACCOUNT_PATTERN = re.compile(
    r"(?i)(?:account|a/c|acct)"
    r"(?:\s*(?:number|no|no\.|#))?"
    r"\s*[:\-#]?\s*"
    r"([x*•]{2,}[0-9]{2,8})"
)

ENTITY_PRIORITY = {

    "account_number": 100,
    "card_number": 100,
    "pan_number": 100,
    "aadhaar_number": 100,
    "upi_id": 100,
    "customer_id": 100,

    "email_address": 90,
    "phone_number": 90,

    "ifsc_code": 80,
}

ACCOUNT_LABEL_PATTERN = re.compile(
    r"(?i)"
    r"(?:account"
    r"(?:\s+number|\s+no\.?|\s*#)?"
    r"|a/c"
    r"|acct\.?"
    r")"
)

MASKED_ACCOUNT_VALUE_PATTERN = re.compile(
    r"(?i)"
    r"[x*•]{2,}[0-9]{2,8}"
)

# ============================================================
# Generic detector helpers
# ============================================================
def normalize_digits(value):
    return re.sub(
        r"[^0-9]",
        "",
        value,
    )

def looks_like_account_number(value):

    digits = normalize_digits(value)

    if not 8 <= len(digits) <= 18:
        return False

    return True

def _matches_from_pattern(
    text,
    pattern,
    entity_type,
):
    matches = []

    for match in pattern.finditer(text):

        matches.append(
            PIIMatch(
                entity_type=entity_type,
                start=match.start(),
                end=match.end(),
                value=match.group(),
                score=1.0,
            )
        )

    return matches


# ============================================================
# Specific financial detectors
# ============================================================

def passes_luhn(number):

    digits = normalize_digits(number)

    if not 13 <= len(digits) <= 19:
        return False

    total = 0

    reverse_digits = digits[::-1]

    for index, digit in enumerate(
        reverse_digits
    ):

        value = int(digit)

        if index % 2 == 1:

            value *= 2

            if value > 9:
                value -= 9

        total += value

    return total % 10 == 0

def detect_card_numbers(text):

    matches = []

    for match in CARD_NUMBER_PATTERN.finditer(text):

        value = match.group(1)

        if passes_luhn(value):

            confidence = 1.0

        else:

            confidence = 0.85

        matches.append(
            PIIMatch(
                entity_type="card_number",
                start=match.start(1),
                end=match.end(1),
                value=value,
                score=confidence,
            )
        )

    return matches

def detect_masked_accounts(text):

    matches = []

    for label_match in ACCOUNT_LABEL_PATTERN.finditer(text):

        # Look immediately after the account label.
        remaining = text[label_match.end():]

        value_match = MASKED_ACCOUNT_VALUE_PATTERN.match(
            remaining.strip()
        )

        if not value_match:
            continue

        # Calculate positions in original text.
        leading_spaces = len(remaining) - len(
            remaining.lstrip()
        )

        start = (
            label_match.end()
            + leading_spaces
            + value_match.start()
        )

        end = (
            label_match.end()
            + leading_spaces
            + value_match.end()
        )

        value = text[start:end]

        matches.append(
            PIIMatch(
                entity_type="account_number",
                start=start,
                end=end,
                value=value,
                score=1.0,
            )
        )

    return matches

def detect_account_numbers(text):

    matches = []

    # Normal account numbers
    for match in ACCOUNT_NUMBER_PATTERN.finditer(text):

        value = match.group(1)

        if looks_like_account_number(value):

            matches.append(
                PIIMatch(
                    entity_type="account_number",
                    start=match.start(1),
                    end=match.end(1),
                    value=value,
                    score=1.0,
                )
            )

    # Masked account numbers
    for match in MASKED_ACCOUNT_PATTERN.finditer(text):

        value = match.group(1)

        matches.append(
            PIIMatch(
                entity_type="account_number",
                start=match.start(1),
                end=match.end(1),
                value=value,
                score=1.0,
            )
        )

    return matches
    
def detect_customer_ids(text):

    matches = []

    for match in CUSTOMER_ID_PATTERN.finditer(text):

        value = match.group(1)

        matches.append(
            PIIMatch(
                entity_type="customer_id",
                start=match.start(1),
                end=match.end(1),
                value=value,
                score=1.0,
            )
        )

    return matches

def detect_upi_ids(text):
    """
    Detect UPI-like identifiers in financial narrations.

    A narration is treated as '-' delimited.

    Any individual segment containing '@' is treated
    as a UPI identifier.

    Example:

        UPI-ZOMATO-zomato@icici-ICICI009182-...

    becomes:

        UPI-ZOMATO-[UPI]-ICICI009182-...
    """

    matches = []

    for part in re.finditer(
        r"[^-]+",
        text,
    ):

        raw_value = part.group()

        if "@" not in raw_value:
            continue

        value = raw_value.strip()

        if not value:
            continue

        # Calculate the exact position of the
        # non-whitespace token in the original text.
        leading_spaces = (
            len(raw_value)
            - len(raw_value.lstrip())
        )

        start = (
            part.start()
            + leading_spaces
        )

        end = start + len(value)

        matches.append(
            PIIMatch(
                entity_type="upi_id",
                start=start,
                end=end,
                value=value,
                score=1.0,
            )
        )

    return matches
# ============================================================
# Main deterministic detector
# ============================================================

def detect_regex_pii(text):

    matches = []

    # Generic PII
    matches.extend(
        _matches_from_pattern(
            text,
            EMAIL_PATTERN,
            "email_address",
        )
    )

    matches.extend(
        _matches_from_pattern(
            text,
            PHONE_PATTERN,
            "phone_number",
        )
    )

    # Indian financial identifiers
    matches.extend(
        _matches_from_pattern(
            text,
            PAN_PATTERN,
            "pan_number",
        )
    )

    matches.extend(
        _matches_from_pattern(
            text,
            AADHAAR_PATTERN,
            "aadhaar_number",
        )
    )

    matches.extend(
        _matches_from_pattern(
            text,
            IFSC_PATTERN,
            "ifsc_code",
        )
    )

    matches.extend(
        detect_upi_ids(text)
    )

    # Context-dependent
    matches.extend(
        detect_account_numbers(text)
    )

    matches.extend(
        detect_card_numbers(text)
    )

    matches.extend(
        detect_customer_ids(text)
    )

    return matches

def remove_overlaps(matches):

    matches = sorted(
        matches,
        key=lambda match: (
            match.start,
            -(match.end - match.start),
            -match.score,
        ),
    )

    result = []

    for match in matches:

        overlaps = False

        for existing in result:

            if (
                match.start < existing.end
                and match.end > existing.start
            ):
                overlaps = True
                break

        if not overlaps:
            result.append(match)

    return sorted(
        result,
        key=lambda match: match.start,
    )

def detect_contextual_matches(
    text,
    pattern,
    entity_type,
):
    matches = []

    for match in pattern.finditer(text):

        value = match.group(1)

        matches.append(
            PIIMatch(
                entity_type=entity_type,
                start=match.start(1),
                end=match.end(1),
                value=value,
                score=1.0,
            )
        )

    return matches

def detect_pii(text):

    matches = detect_regex_pii(text)

    return remove_overlaps(
        matches
    )