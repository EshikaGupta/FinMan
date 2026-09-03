from collections import defaultdict

from ..database import get_account_transactions, get_transactions
from .categorizer import categorize_transaction


# Categories that can reasonably be described as potentially discretionary.
# This is intentionally a broad classification, not a claim that any expense
# in these categories is unnecessary.
POTENTIALLY_DISCRETIONARY_CATEGORIES = {
    "Food",
    "Shopping",
    "Entertainment",
}


def _category(transaction):
    return transaction.category or categorize_transaction(transaction.description)


def _merchant(transaction):
    return transaction.merchant or transaction.description or "Unknown"


def detect_subscriptions(transactions):
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
        amount = transaction.debit if transaction.debit is not None else 0.0
        item["amount"] += amount
        item["charge_count"] += 1
        if transaction.date > item["last_charge_date"]:
            item["last_charge_date"] = transaction.date

    return [
        {**item, "amount": round(item["amount"], 2)}
        for item in sorted(
            grouped.values(),
            key=lambda item: item["amount"],
            reverse=True,
        )
    ]


def _analyze_transactions(transactions, scope_id, scope_type):
    if not transactions:
        raise ValueError("No transactions found.")

    total_income = 0.0
    total_spending = 0.0
    salary_income = 0.0
    salary_transactions = []
    category_totals = defaultdict(float)
    merchant_totals = defaultdict(float)
    income_category_totals = defaultdict(float)
    monthly_totals = defaultdict(lambda: {"income": 0.0, "spending": 0.0})
    investment_transactions = []
    potentially_discretionary_totals = defaultdict(float)
    largest_expenses = []

    for transaction in transactions:
        debit = transaction.debit or 0.0
        credit = transaction.credit or 0.0
        month = str(transaction.date)[:7]
        category = _category(transaction)
        merchant = _merchant(transaction)

        if credit > 0:
            total_income += credit
            monthly_totals[month]["income"] += credit
            income_category_totals[category] += credit

            if category == "Salary":
                salary_income += credit
                salary_transactions.append({
                    "date": transaction.date,
                    "description": transaction.description,
                    "merchant": transaction.merchant or "",
                    "amount": credit,
                    "category": category,
                })

        if debit > 0:
            total_spending += debit
            monthly_totals[month]["spending"] += debit
            category_totals[category] += debit
            merchant_totals[merchant] += debit

            if category == "Investments":
                investment_transactions.append({
                    "date": transaction.date,
                    "amount": debit,
                    "merchant": transaction.merchant or "",
                })

            if category in POTENTIALLY_DISCRETIONARY_CATEGORIES:
                potentially_discretionary_totals[category] += debit

            largest_expenses.append({
                "date": transaction.date,
                "description": transaction.description,
                "merchant": transaction.merchant or "",
                "amount": debit,
                "category": category,
                "is_subscription": transaction.is_subscription,
            })

    largest_expenses.sort(key=lambda item: item["amount"], reverse=True)
    subscriptions = detect_subscriptions(transactions)

    formatted_monthly_totals = {
        month: {
            "income": round(values["income"], 2),
            "spending": round(values["spending"], 2),
            "net": round(values["income"] - values["spending"], 2),
        }
        for month, values in sorted(monthly_totals.items())
    }

    net_cash_flow = total_income - total_spending
    savings_rate = (net_cash_flow / total_income * 100) if total_income > 0 else None

    investment_total = sum(
        item["amount"] for item in investment_transactions
    )

    recurring_expense_total = sum(
        item["amount"] for item in subscriptions
    )

    category_share_of_spending = {
        category: round((amount / total_spending * 100), 2)
        for category, amount in category_totals.items()
        if total_spending > 0
    }

    subscription_share_of_spending = (
        round((recurring_expense_total / total_spending * 100), 2)
        if total_spending > 0
        else None
    )

    investment_share_of_income = (
        round((investment_total / total_income * 100), 2)
        if total_income > 0
        else None
    )

    discretionary_total = sum(
        potentially_discretionary_totals.values()
    )
    discretionary_share_of_spending = (
        round((discretionary_total / total_spending * 100), 2)
        if total_spending > 0
        else None
    )

    result = {
        f"{scope_type}_id": scope_id,
        "transaction_count": len(transactions),
        "total_income": round(total_income, 2),
        "salary_income": round(salary_income, 2),
        "salary_transaction_count": len(salary_transactions),
        "salary_transactions": salary_transactions,
        "income_category_totals": dict(
            sorted(
                ((c, round(v, 2)) for c, v in income_category_totals.items()),
                key=lambda item: item[1],
                reverse=True,
            )
        ),
        "total_spending": round(total_spending, 2),
        "net_cash_flow": round(net_cash_flow, 2),
        "savings_rate": round(savings_rate, 2) if savings_rate is not None else None,
        "category_totals": dict(
            sorted(
                ((c, round(v, 2)) for c, v in category_totals.items()),
                key=lambda item: item[1],
                reverse=True,
            )
        ),
        "category_share_of_spending": dict(
            sorted(
                category_share_of_spending.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ),
        "merchant_totals": dict(
            sorted(
                ((m, round(v, 2)) for m, v in merchant_totals.items()),
                key=lambda item: item[1],
                reverse=True,
            )
        ),
        "monthly_totals": formatted_monthly_totals,
        "subscriptions": subscriptions,
        "subscription_count": len(subscriptions),
        "recurring_expense_total": round(recurring_expense_total, 2),
        "subscription_share_of_spending": subscription_share_of_spending,
        "investment_activity": {
            "total": round(investment_total, 2),
            "transaction_count": len(investment_transactions),
            "share_of_income": investment_share_of_income,
            "transactions": investment_transactions,
        },
        "potentially_discretionary_spending": {
            "total": round(discretionary_total, 2),
            "share_of_spending": discretionary_share_of_spending,
            "categories": dict(
                sorted(
                    (
                        (c, round(v, 2))
                        for c, v in potentially_discretionary_totals.items()
                    ),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ),
        },
        "largest_expenses": largest_expenses[:10],
    }
    return result


def analyze_statement(statement_id):
    return _analyze_transactions(
        get_transactions(statement_id),
        statement_id,
        "statement",
    )


def analyze_account(account_id):
    return _analyze_transactions(
        get_account_transactions(account_id),
        account_id,
        "account",
    )