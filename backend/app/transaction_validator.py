from typing import List

from .schemas import Transaction


class TransactionValidationError(
    Exception
):
    pass

def has_amount(value):
    if value is None:
        return False

    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False

def validate_transactions(
    transactions: List[Transaction],
):
    if not transactions:
        raise TransactionValidationError(
            "No transactions found."
        )

    for index, transaction in enumerate(
        transactions
    ):

        # -----------------------------------------
        # Required fields
        # -----------------------------------------

        if not transaction.date.strip():

            raise TransactionValidationError(
                f"Transaction {index + 1}: "
                "missing date."
            )

        if not transaction.description.strip():

            raise TransactionValidationError(
                f"Transaction {index + 1}: "
                "missing description."
            )

        # -----------------------------------------
        # Debit and credit cannot both exist
        # -----------------------------------------

        debit_present = has_amount(
            transaction.debit
        )

        credit_present = has_amount(
            transaction.credit
        )

        if debit_present and credit_present:
            raise ValueError(
                f"Transaction {index}: "
                "both debit and credit are present."
            )

        if not debit_present and not credit_present:
            raise ValueError(
                f"Transaction {index}: "
                "neither debit nor credit is present."
            )

        # -----------------------------------------
        # Amounts must not be negative
        # -----------------------------------------

        if (
            transaction.debit is not None
            and transaction.debit < 0
        ):

            raise TransactionValidationError(
                f"Transaction {index + 1}: "
                "negative debit."
            )

        if (
            transaction.credit is not None
            and transaction.credit < 0
        ):

            raise TransactionValidationError(
                f"Transaction {index + 1}: "
                "negative credit."
            )

    return transactions