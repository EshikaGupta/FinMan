from typing import Optional
import re


# ---------------------------------------------------------
# Known merchants → categories
#
# These are primarily used as deterministic fallback rules.
# Gemini remains the primary categorization engine.
# ---------------------------------------------------------

MERCHANT_CATEGORIES = {
    # Food
    "swiggy": "Food",
    "zomato": "Food",
    "dominos": "Food",
    "mcdonald": "Food",
    "mcdonalds": "Food",
    "kfc": "Food",

    # Transport
    "uber": "Transport",
    "ola": "Transport",
    "rapido": "Transport",
    "metro": "Transport",

    # Shopping
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "ajio": "Shopping",
    "nykaa": "Shopping",

    # Entertainment
    "netflix": "Entertainment",
    "spotify": "Entertainment",
    "bookmyshow": "Entertainment",

    # Bills & Utilities
    "electricity": "Bills & Utilities",
    "bescom": "Bills & Utilities",
    "water": "Bills & Utilities",
    "airtel": "Bills & Utilities",
    "jio": "Bills & Utilities",
    "vodafone": "Bills & Utilities",
    "rent": "Bills & Utilities",

    # Investments
    "sip": "Investments",
    "mutual fund": "Investments",
    "zerodha": "Investments",
    "groww": "Investments",
    "investment": "Investments",

    # Income / other
    "salary": "Salary",
    "refund": "Refund",
    "cash withdrawal": "Cash Withdrawal",
}


# ---------------------------------------------------------
# Actual recognizable merchants.
#
# This is deliberately separate from MERCHANT_CATEGORIES.
# A category keyword like "salary" is NOT a merchant.
# ---------------------------------------------------------

KNOWN_MERCHANTS = {
    "swiggy": "Swiggy",
    "zomato": "Zomato",
    "dominos": "Dominos",
    "mcdonald": "McDonald's",
    "mcdonalds": "McDonald's",
    "kfc": "KFC",

    "uber": "Uber",
    "ola": "Ola",
    "rapido": "Rapido",
    "metro": "Metro",

    "amazon": "Amazon",
    "flipkart": "Flipkart",
    "myntra": "Myntra",
    "ajio": "AJIO",
    "nykaa": "Nykaa",

    "netflix": "Netflix",
    "spotify": "Spotify",
    "bookmyshow": "BookMyShow",

    "airtel": "Airtel",
    "jio": "Jio",
    "vodafone": "Vodafone",

    "zerodha": "Zerodha",
    "groww": "Groww",
}


def categorize_transaction(
    description: str,
) -> str:
    """
    Deterministic fallback category.

    Searches the COMPLETE narration rather than only
    the beginning of the transaction.
    """

    description_lower = (
        description or ""
    ).lower()

    for merchant, category in (
        MERCHANT_CATEGORIES.items()
    ):
        if merchant in description_lower:
            return category

    return "Other"


def _clean_candidate(value: str) -> str:
    """
    Clean a possible merchant/person name extracted
    from a transaction narration.
    """

    value = value.strip()

    if not value:
        return ""

    # Don't expose PII placeholders as merchants.
    if "<pii:" in value.lower():
        return ""

    # Remove common whitespace noise.
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _known_merchant_from_text(
    description: str,
) -> Optional[str]:
    """
    Search the complete narration for a known merchant.
    """

    description_lower = (
        description or ""
    ).lower()

    for merchant, display_name in (
        KNOWN_MERCHANTS.items()
    ):
        if merchant in description_lower:
            return display_name

    return None


def _extract_upi_name(
    description: str,
) -> Optional[str]:
    """
    Extract the person/merchant name from common UPI
    narration formats.

    Example:

        UPI-RAHUL VERMA-rahul.92@okhdfc-HDFC001781-...

    becomes:

        Rahul Verma

    The UPI ID itself is never returned.
    """

    if not description:
        return None

    text = description.strip()

    if not text.upper().startswith("UPI-"):
        return None

    parts = text.split("-")

    if len(parts) < 2:
        return None

    candidate = _clean_candidate(
        parts[1]
    )

    if not candidate:
        return None

    # If the second segment itself looks like an email/UPI ID,
    # don't expose it.
    if "@" in candidate:
        return None

    # Don't return transaction/reference placeholders.
    if candidate.lower().startswith(
        (
            "<pii:",
            "transaction_reference",
            "upi_id",
        )
    ):
        return None

    return candidate.title()


def _extract_pos_merchant(
    description: str,
) -> Optional[str]:
    """
    Extract merchant from POS-style narration.

    Example:

        POS-AMAZON INDIA-ORDER 405-...

    becomes:

        Amazon India
    """

    if not description:
        return None

    text = description.strip()

    if not text.upper().startswith("POS-"):
        return None

    parts = text.split("-")

    if len(parts) < 2:
        return None

    candidate = _clean_candidate(
        parts[1]
    )

    if not candidate:
        return None

    return candidate.title()


def detect_merchant(
    description: str,
) -> Optional[str]:
    """
    Extract a useful merchant/payee name.

    Priority:

    1. Known merchant anywhere in narration
    2. UPI person/merchant name
    3. POS merchant
    4. None

    This intentionally does NOT use category names such as
    'Salary', 'Food', 'Rent', etc. as merchant names.
    """

    if not description:
        return None

    # First prefer recognizable merchants.
    #
    # This is important for:
    #
    # UPI-ZOMATO-zomato@...
    #
    # where we want Zomato rather than a generic
    # UPI counterparty name.
    known = _known_merchant_from_text(
        description
    )

    if known:
        return known

    # UPI person/payee.
    upi_name = _extract_upi_name(
        description
    )

    if upi_name:
        return upi_name

    # POS merchant.
    pos_name = _extract_pos_merchant(
        description
    )

    if pos_name:
        return pos_name

    return None


def is_autopay(
    description: str,
) -> bool:
    """
    Detect subscription/autopay transactions.

    This is deterministic and does not depend on Gemini.
    """

    return (
        "autopay"
        in (description or "").lower()
    )