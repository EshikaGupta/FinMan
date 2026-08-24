from ..analysis.service import detect_subscriptions
from ..database import get_transactions


def list_transactions(statement_id):
    return get_transactions(statement_id)


def list_subscriptions(statement_id):
    transactions = get_transactions(statement_id)
    return detect_subscriptions(transactions)
