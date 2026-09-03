import re


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
        r"(?P<value>[A-Za-z0-9][A-Za-z0-9\-/]{5,})"
    ),
]

# Common bank-generated references such as HDFC001234.
BANK_REFERENCE_PATTERN = re.compile(
    r"\b[A-Z]{4}\d{6,}\b"
)

_REFERENCE_PLACEHOLDER = "__FINMAN_TRANSACTION_REFERENCE_{index}__"


def _reference_matches(text):
    matches = []

    for pattern in REFERENCE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.groupdict().get("value") or match.group()
            value_start = match.start("value") if "value" in match.groupdict() else match.start()
            value_end = match.end("value") if "value" in match.groupdict() else match.end()
            matches.append((value_start, value_end, value))

    for match in BANK_REFERENCE_PATTERN.finditer(text):
        matches.append((match.start(), match.end(), match.group()))

    # Keep the longest match when spans overlap.
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    filtered = []
    for item in matches:
        if filtered and item[0] < filtered[-1][1]:
            continue
        filtered.append(item)
    return filtered


def extract_transaction_reference(text):
    """Extract the bank/provider transaction reference from a narration.

    References are intentionally kept in the stored narration because they
    are useful for deterministic transaction deduplication. Returns None when
    the narration does not contain a recognizable reference.
    """
    if text is None:
        return None

    text = str(text)
    matches = _reference_matches(text)
    if not matches:
        return None

    # Prefer an explicit labelled reference over a generic bank-style token.
    for pattern in REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group("value")

    return matches[0][2]


def _protect_references(text):
    """Temporarily protect references from generic PII redaction."""
    matches = _reference_matches(text)
    if not matches:
        return text, {}

    output = []
    replacements = {}
    last = 0

    for index, (start, end, value) in enumerate(matches):
        output.append(text[last:start])
        placeholder = _REFERENCE_PLACEHOLDER.format(index=index)
        output.append(placeholder)
        replacements[placeholder] = value
        last = end

    output.append(text[last:])
    return "".join(output), replacements


def sanitize_narration(text):
    """Sanitize narration while preserving transaction references.

    Merchant/payee names and bank transaction references are preserved. Other
    high-confidence PII (UPI IDs, account/card numbers, phone, email, etc.) is
    still redacted by the normal PII detector.
    """
    if text is None:
        return text

    text = str(text)
    if not text.strip():
        return text

    # Import locally to avoid a module cycle and protect transaction
    # references before the generic PII detector sees them.
    from .redactor import Redactor

    protected_text, replacements = _protect_references(text)
    result = Redactor().redact(protected_text).text

    for placeholder, original in replacements.items():
        result = result.replace(placeholder, original)

    return result