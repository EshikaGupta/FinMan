import hashlib
import json
from decimal import Decimal, InvalidOperation

from .transaction_dedup import build_transaction_fingerprint, normalize_date


def _number(value):
    if value is None:
        return None
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError, TypeError):
        return None


def build_statement_identity(account_id, transactions):
    """Build Level 2 identity from canonical financial transaction content.

    Filename, upload timestamp and file metadata are excluded. Transaction
    order is also ignored because exports can reorder rows without changing
    the underlying statement. Duplicate rows remain duplicated in the sorted
    list, so the transaction count/multiplicity is preserved.
    """
    if not transactions:
        raise ValueError("Cannot build statement identity without transactions.")

    transaction_keys = []
    for transaction in transactions:
        transaction_keys.append(
            {
                "fingerprint": build_transaction_fingerprint(transaction),
                "balance": _number(transaction.balance),
            }
        )

    transaction_keys.sort(
        key=lambda item: (item["fingerprint"], item["balance"] or "")
    )

    payload = {
        "account_id": account_id,
        "transaction_count": len(transactions),
        "transactions": transaction_keys,
    }

    digest = hashlib.sha256(
        json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()

    dates = [
        normalize_date(t.date)
        for t in transactions
        if str(t.date or "").strip()
    ]
    debits = sum(
        (Decimal(str(t.debit)) for t in transactions if t.debit is not None),
        Decimal("0"),
    )
    credits = sum(
        (Decimal(str(t.credit)) for t in transactions if t.credit is not None),
        Decimal("0"),
    )

    return {
        "fingerprint": digest,
        "period_start": min(dates) if dates else None,
        "period_end": max(dates) if dates else None,
        "transaction_count": len(transactions),
        "total_debit": float(debits),
        "total_credit": float(credits),
    }


def get_file_hash(content):
    return hashlib.sha256(content).hexdigest()


def get_file_format(filename):
    if "." not in filename:
        return None
    return filename.rsplit(".", 1)[-1].lower()