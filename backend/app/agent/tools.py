from typing import Any

from ..database import get_transactions


def _get_value(transaction, field, default=None):
    """
    Read a transaction field regardless of whether the
    transaction is a dict, sqlite Row, or Pydantic model.
    """

    if isinstance(transaction, dict):
        return transaction.get(field, default)

    try:
        return transaction[field]
    except (KeyError, TypeError, IndexError):
        pass

    return getattr(
        transaction,
        field,
        default,
    )


def _row_to_dict(transaction):
    """
    Convert a transaction into a JSON-safe dictionary.
    """

    return {
        "date": _get_value(transaction, "date"),
        "description": _get_value(
            transaction,
            "description",
            "",
        ),
        "debit": _get_value(
            transaction,
            "debit",
        ),
        "credit": _get_value(
            transaction,
            "credit",
        ),
        "balance": _get_value(
            transaction,
            "balance",
        ),
        "category": _get_value(
            transaction,
            "category",
            "",
        ),
        "merchant": _get_value(
            transaction,
            "merchant",
            "",
        ),
        "is_subscription": _get_value(
            transaction,
            "is_subscription",
            False,
        ),
    }


def get_statement_transactions(
    statement_id: int,
):
    """
    Return all transactions belonging to a statement.
    """

    rows = get_transactions(
        statement_id
    )

    return [
        _row_to_dict(row)
        for row in rows
    ]


def search_transactions(
    statement_id: int,
    query: str,
    limit: int = 20,
):
    """
    Retrieve transactions relevant to a natural-language query.

    Searches across:
    - merchant
    - description
    - category

    Results are ranked by relevance.
    """

    query = (query or "").strip().lower()

    if not query:
        return []

    transactions = get_statement_transactions(
        statement_id
    )

    query_tokens = [
        token
        for token in query.split()
        if len(token) >= 2
    ]

    results = []

    for transaction in transactions:

        merchant = str(
            transaction.get("merchant")
            or ""
        ).lower()

        description = str(
            transaction.get("description")
            or ""
        ).lower()

        category = str(
            transaction.get("category")
            or ""
        ).lower()

        searchable_text = " ".join(
            [
                merchant,
                description,
                category,
            ]
        )

        score = 0

        # Exact phrase match
        if query in merchant:
            score += 100

        if query in description:
            score += 80

        if query in category:
            score += 50

        # Token matches
        for token in query_tokens:

            if token in merchant:
                score += 30

            if token in description:
                score += 20

            if token in category:
                score += 10

        if score > 0:
            results.append(
                (
                    score,
                    transaction,
                )
            )

    results.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        transaction
        for _, transaction
        in results[:limit]
    ]


def get_spending_by_category(
    statement_id: int,
):
    """
    Return total spending grouped by category.
    """

    transactions = get_statement_transactions(
        statement_id
    )

    totals = {}

    for transaction in transactions:

        debit = transaction.get(
            "debit"
        ) or 0

        if debit <= 0:
            continue

        category = (
            transaction.get("category")
            or "Other"
        )

        totals[category] = (
            totals.get(category, 0)
            + debit
        )

    return dict(
        sorted(
            totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )


def get_spending_by_merchant(
    statement_id: int,
):
    """
    Return total spending grouped by merchant.
    """

    transactions = get_statement_transactions(
        statement_id
    )

    totals = {}

    for transaction in transactions:

        debit = transaction.get(
            "debit"
        ) or 0

        if debit <= 0:
            continue

        merchant = (
            transaction.get("merchant")
            or "Unknown"
        )

        totals[merchant] = (
            totals.get(merchant, 0)
            + debit
        )

    return dict(
        sorted(
            totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )


def get_income(
    statement_id: int,
):
    """
    Return income transactions and total income.
    """

    transactions = get_statement_transactions(
        statement_id
    )

    income_transactions = [
        transaction
        for transaction in transactions
        if (
            transaction.get("credit")
            or 0
        ) > 0
    ]

    total = sum(
        transaction.get("credit")
        or 0
        for transaction
        in income_transactions
    )

    return {
        "total_income": round(
            total,
            2,
        ),
        "transactions": income_transactions,
    }


def get_largest_expenses(
    statement_id: int,
    limit: int = 10,
):
    """
    Return the largest debit transactions.
    """

    transactions = get_statement_transactions(
        statement_id
    )

    expenses = [
        transaction
        for transaction in transactions
        if (
            transaction.get("debit")
            or 0
        ) > 0
    ]

    expenses.sort(
        key=lambda transaction:
        transaction.get("debit") or 0,
        reverse=True,
    )

    return expenses[:limit]


def get_financial_summary(
    statement_id: int,
):
    """
    Return the basic financial picture
    for a statement.
    """

    transactions = get_statement_transactions(
        statement_id
    )

    total_income = sum(
        transaction.get("credit")
        or 0
        for transaction
        in transactions
    )

    total_spending = sum(
        transaction.get("debit")
        or 0
        for transaction
        in transactions
    )

    return {
        "statement_id": statement_id,
        "transaction_count": len(
            transactions
        ),
        "total_income": round(
            total_income,
            2,
        ),
        "total_spending": round(
            total_spending,
            2,
        ),
        "net_cash_flow": round(
            total_income - total_spending,
            2,
        ),
    }


def get_subscriptions(
    statement_id: int,
):
    """
    Return transactions detected as subscriptions.
    """

    transactions = get_statement_transactions(
        statement_id
    )

    return [
        transaction
        for transaction in transactions
        if transaction.get(
            "is_subscription",
            False,
        )
    ]