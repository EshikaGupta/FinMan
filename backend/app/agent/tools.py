from ..database import get_account_transactions


def _row_to_dict(transaction):
    return {
        "date": transaction.date,
        "description": transaction.description,
        "debit": transaction.debit,
        "credit": transaction.credit,
        "balance": transaction.balance,
        "category": transaction.category or "",
        "merchant": transaction.merchant or "",
        "is_subscription": transaction.is_subscription,
    }


def get_account_transactions_for_agent(account_id):
    return [_row_to_dict(row) for row in get_account_transactions(account_id)]


def search_transactions(account_id, query, limit=20):
    query = (query or "").strip().lower()
    if not query:
        return []
    transactions = get_account_transactions_for_agent(account_id)
    query_tokens = [token for token in query.split() if len(token) >= 2]
    results = []
    for transaction in transactions:
        merchant = str(transaction.get("merchant") or "").lower()
        description = str(transaction.get("description") or "").lower()
        category = str(transaction.get("category") or "").lower()
        score = 0
        if query in merchant: score += 100
        if query in description: score += 80
        if query in category: score += 50
        for token in query_tokens:
            if token in merchant: score += 30
            if token in description: score += 20
            if token in category: score += 10
        if score > 0:
            results.append((score, transaction))
    results.sort(key=lambda item: item[0], reverse=True)
    return [transaction for _, transaction in results[:limit]]


def get_spending_by_category(account_id):
    totals = {}
    for transaction in get_account_transactions_for_agent(account_id):
        debit = transaction.get("debit") or 0
        if debit <= 0: continue
        category = transaction.get("category") or "Other"
        totals[category] = totals.get(category, 0) + debit
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))


def get_spending_by_merchant(account_id):
    totals = {}
    for transaction in get_account_transactions_for_agent(account_id):
        debit = transaction.get("debit") or 0
        if debit <= 0: continue
        merchant = transaction.get("merchant") or "Unknown"
        totals[merchant] = totals.get(merchant, 0) + debit
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))


def get_income(account_id):
    transactions = get_account_transactions_for_agent(account_id)
    income = [t for t in transactions if (t.get("credit") or 0) > 0]
    return {"total_income": round(sum(t.get("credit") or 0 for t in income), 2), "transactions": income}


def get_largest_expenses(account_id, limit=10):
    transactions = get_account_transactions_for_agent(account_id)
    expenses = [t for t in transactions if (t.get("debit") or 0) > 0]
    expenses.sort(key=lambda t: t.get("debit") or 0, reverse=True)
    return expenses[:limit]


def get_financial_summary(account_id):
    transactions = get_account_transactions_for_agent(account_id)
    income = sum(t.get("credit") or 0 for t in transactions)
    spending = sum(t.get("debit") or 0 for t in transactions)
    return {
        "account_id": account_id,
        "transaction_count": len(transactions),
        "total_income": round(income, 2),
        "total_spending": round(spending, 2),
        "net_cash_flow": round(income - spending, 2),
    }


def get_subscriptions(account_id):
    return [t for t in get_account_transactions_for_agent(account_id) if t.get("is_subscription", False)]