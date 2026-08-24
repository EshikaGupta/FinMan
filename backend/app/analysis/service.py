from collections import defaultdict

from ..database import get_transactions
from .categorizer import categorize_transaction


def _category(transaction):
    return (
        transaction.category
        or categorize_transaction(
            transaction.description
        )
    )


def _merchant(transaction):
    return (
        transaction.merchant
        or transaction.description
        or "Unknown"
    )


def detect_subscriptions(transactions):
    """
    Detect subscriptions using the current explicit signal:
    the narration contains the word AUTOPAY.

    Results are grouped by merchant when available.
    """

    grouped = {}

    for transaction in transactions:

        if not transaction.is_subscription:
            continue

        merchant = _merchant(transaction)

        key = merchant.lower()

        item = grouped.setdefault(
            key,
            {
                "merchant": merchant,
                "amount": 0.0,
                "charge_count": 0,
                "last_charge_date": transaction.date,
                "category": _category(transaction),
            },
        )

        amount = (
            transaction.debit
            if transaction.debit is not None
            else 0.0
        )

        item["amount"] += amount
        item["charge_count"] += 1

        if transaction.date > item["last_charge_date"]:
            item["last_charge_date"] = transaction.date

    return [
        {
            **item,
            "amount": round(item["amount"], 2),
        }
        for item in sorted(
            grouped.values(),
            key=lambda item: item["amount"],
            reverse=True,
        )
    ]


def analyze_statement(statement_id):

    transactions = get_transactions(
        statement_id
    )

    if not transactions:
        raise ValueError(
            "No transactions found."
        )

    # --------------------------------------------------
    # Overall totals
    # --------------------------------------------------

    total_income = 0.0
    total_spending = 0.0

    # --------------------------------------------------
    # Salary
    # --------------------------------------------------

    salary_income = 0.0
    salary_transactions = []

    # --------------------------------------------------
    # Aggregations
    # --------------------------------------------------

    category_totals = defaultdict(float)
    merchant_totals = defaultdict(float)

    monthly_totals = defaultdict(
        lambda: {
            "income": 0.0,
            "spending": 0.0,
        }
    )

    largest_expenses = []

    # --------------------------------------------------
    # Process transactions
    # --------------------------------------------------

    for transaction in transactions:

        debit = transaction.debit or 0.0
        credit = transaction.credit or 0.0

        month = str(transaction.date)[:7]

        category = _category(transaction)
        merchant = _merchant(transaction)

        # ----------------------------------------------
        # Income
        # ----------------------------------------------

        if credit > 0:

            total_income += credit

            monthly_totals[
                month
            ]["income"] += credit

            # Salary is a subset of total income
            if category == "Salary":

                salary_income += credit

                salary_transactions.append(
                    {
                        "date": transaction.date,
                        "description": transaction.description,
                        "merchant": (
                            transaction.merchant
                            or ""
                        ),
                        "amount": credit,
                        "category": category,
                    }
                )

        # ----------------------------------------------
        # Spending
        # ----------------------------------------------

        if debit > 0:

            total_spending += debit

            monthly_totals[
                month
            ]["spending"] += debit

            category_totals[
                category
            ] += debit

            merchant_totals[
                merchant
            ] += debit

            largest_expenses.append(
                {
                    "date": transaction.date,
                    "description": transaction.description,
                    "merchant": (
                        transaction.merchant
                        or ""
                    ),
                    "amount": debit,
                    "category": category,
                    "is_subscription": (
                        transaction.is_subscription
                    ),
                }
            )

    # --------------------------------------------------
    # Sort largest expenses
    # --------------------------------------------------

    largest_expenses.sort(
        key=lambda item: item["amount"],
        reverse=True,
    )

    # --------------------------------------------------
    # Subscriptions
    # --------------------------------------------------

    subscriptions = detect_subscriptions(
        transactions
    )

    # --------------------------------------------------
    # Monthly totals
    # --------------------------------------------------

    formatted_monthly_totals = {
        month: {
            "income": round(
                values["income"],
                2,
            ),
            "spending": round(
                values["spending"],
                2,
            ),
            "net": round(
                values["income"]
                - values["spending"],
                2,
            ),
        }
        for month, values in sorted(
            monthly_totals.items()
        )
    }

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    return {
        "statement_id": statement_id,

        "transaction_count": len(
            transactions
        ),

        # Overall income
        "total_income": round(
            total_income,
            2,
        ),

        # Salary specifically
        "salary_income": round(
            salary_income,
            2,
        ),

        "salary_transaction_count": len(
            salary_transactions
        ),

        "salary_transactions": salary_transactions,

        # Overall spending
        "total_spending": round(
            total_spending,
            2,
        ),

        # Net
        "net_cash_flow": round(
            total_income
            - total_spending,
            2,
        ),

        # Categories
        "category_totals": dict(
            sorted(
                (
                    (
                        category,
                        round(
                            amount,
                            2,
                        ),
                    )
                    for category, amount
                    in category_totals.items()
                ),
                key=lambda item: item[1],
                reverse=True,
            )
        ),

        # Merchants
        "merchant_totals": dict(
            sorted(
                (
                    (
                        merchant,
                        round(
                            amount,
                            2,
                        ),
                    )
                    for merchant, amount
                    in merchant_totals.items()
                ),
                key=lambda item: item[1],
                reverse=True,
            )
        ),

        # Monthly
        "monthly_totals": (
            formatted_monthly_totals
        ),

        # Subscriptions
        "subscriptions": subscriptions,

        "subscription_count": len(
            subscriptions
        ),

        # Largest expenses
        "largest_expenses": (
            largest_expenses[:10]
        ),
    }