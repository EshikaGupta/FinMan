"""Deterministic transaction identity and matching.

The matcher deliberately does not use an LLM. Bank transaction references are
used as the strongest identity signal; when a reference is unavailable, the
matcher compares normalized financial fields and balance context.
"""

import hashlib
import re
from datetime import datetime
from difflib import SequenceMatcher

from ..pii.narration import extract_transaction_reference


def normalize_text(value):
    value = "" if value is None else str(value)
    value = value.lower()
    value = re.sub(r"<[^>]*>", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_date(value):
    raw = "" if value is None else str(value).strip()
    if not raw:
        return ""

    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d %b %Y",
        "%d %B %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(raw[:10] if fmt == "%Y-%m-%d" else raw, fmt).date().isoformat()
        except ValueError:
            continue

    # Handle ISO datetimes without adding a dependency.
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return raw


def signed_amount(transaction):
    debit = float(transaction.debit or 0)
    credit = float(transaction.credit or 0)
    if debit > 0:
        return -round(debit, 2)
    if credit > 0:
        return round(credit, 2)
    return 0.0


def transaction_type(transaction):
    if float(transaction.debit or 0) > 0:
        return "debit"
    if float(transaction.credit or 0) > 0:
        return "credit"
    return "unknown"


def transaction_reference(transaction):
    return (
        transaction.external_transaction_id
        or extract_transaction_reference(transaction.description)
        or None
    )


def build_transaction_fingerprint(transaction):
    """Stable identity candidate excluding balance.

    Balance is deliberately not part of the fingerprint because the same
    transaction can appear in a statement with missing/variant balance data.
    Balance is instead used as matching evidence.
    """
    payload = "|".join(
        (
            normalize_date(transaction.date),
            f"{signed_amount(transaction):.2f}",
            transaction_type(transaction),
            normalize_text(transaction.description),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _balance_equal(a, b):
    if a is None or b is None:
        return None
    return round(float(a), 2) == round(float(b), 2)


def match_transaction(new_transaction, existing_transaction):
    """Return (score, reason, is_duplicate) for two transactions."""
    new_ref = transaction_reference(new_transaction)
    old_ref = transaction_reference(existing_transaction)

    # A bank reference is the strongest signal available.
    if new_ref and old_ref:
        if normalize_text(new_ref) == normalize_text(old_ref):
            return 1.0, "same_transaction_reference", True
        return 0.0, "different_transaction_reference", False

    if normalize_date(new_transaction.date) != normalize_date(existing_transaction.date):
        return 0.0, "different_date", False

    if signed_amount(new_transaction) != signed_amount(existing_transaction):
        return 0.0, "different_amount", False

    if transaction_type(new_transaction) != transaction_type(existing_transaction):
        return 0.0, "different_transaction_type", False

    new_description = normalize_text(new_transaction.description)
    old_description = normalize_text(existing_transaction.description)
    narration_similarity = SequenceMatcher(None, new_description, old_description).ratio()

    score = 0.0
    score += 0.40  # exact date
    score += 0.35  # exact signed amount/type
    score += 0.20 * narration_similarity

    balance_match = _balance_equal(new_transaction.balance, existing_transaction.balance)
    if balance_match is True:
        score += 0.15
    elif balance_match is False:
        score -= 0.10

    # If a reference exists on only one side, it is useful evidence but not a
    # hard requirement because some statement exports omit references.
    if new_ref or old_ref:
        score += 0.05 if new_ref == old_ref else 0.0

    score = max(0.0, min(1.0, score))
    return score, "field_and_narration_match", score >= 0.80


def build_candidate_indexes(existing_transactions):
    """Build cheap lookup buckets before doing fuzzy comparisons."""
    indexes = {
        "reference": {},
        "fingerprint": {},
        "date_amount": {},
    }

    for transaction_id, transaction in existing_transactions:
        reference = transaction_reference(transaction)
        if reference:
            indexes["reference"].setdefault(normalize_text(reference), []).append(
                (transaction_id, transaction)
            )

        fingerprint = build_transaction_fingerprint(transaction)
        indexes["fingerprint"].setdefault(fingerprint, []).append(
            (transaction_id, transaction)
        )

        date_amount = (
            normalize_date(transaction.date),
            f"{signed_amount(transaction):.2f}",
            transaction_type(transaction),
        )
        indexes["date_amount"].setdefault(date_amount, []).append(
            (transaction_id, transaction)
        )

    return indexes


def find_best_transaction_match(
    new_transaction,
    existing_transactions,
    used_ids=None,
    indexes=None,
):
    """Find the best existing transaction without reusing a match in one import."""
    used_ids = used_ids or set()

    if indexes is None:
        indexes = build_candidate_indexes(existing_transactions)

    reference = transaction_reference(new_transaction)
    if reference:
        candidates = indexes["reference"].get(normalize_text(reference), [])
        if candidates:
            for transaction_id, transaction in candidates:
                if transaction_id not in used_ids:
                    return (1.0, "same_transaction_reference", transaction_id)

    fingerprint = build_transaction_fingerprint(new_transaction)
    candidates = list(indexes["fingerprint"].get(fingerprint, []))

    date_amount = (
        normalize_date(new_transaction.date),
        f"{signed_amount(new_transaction):.2f}",
        transaction_type(new_transaction),
    )
    for candidate in indexes["date_amount"].get(date_amount, []):
        if candidate[0] not in {item[0] for item in candidates}:
            candidates.append(candidate)

    best = None
    for existing_id, existing_transaction in candidates:
        if existing_id in used_ids:
            continue

        existing_reference = transaction_reference(existing_transaction)
        if reference and existing_reference and normalize_text(reference) != normalize_text(existing_reference):
            continue

        score, reason, is_duplicate = match_transaction(
            new_transaction,
            existing_transaction,
        )

        if is_duplicate and (best is None or score > best[0]):
            best = (score, reason, existing_id)

    return best