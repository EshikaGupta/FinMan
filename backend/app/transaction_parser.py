import pandas as pd

from .schemas import (
    ColumnMapping,
    Transaction,
)
from .pii.narration import extract_transaction_reference
from numbers import Integral


def get_value(
    row,
    column,
):
    if column is None:
        return None

    return row[column]


def to_float(value):

    if pd.isna(value):
        return None

    if isinstance(value, str):

        value = (
            value
            .replace(",", "")
            .replace("₹", "")
            .strip()
        )

        if not value:
            return None

    try:
        return float(value)

    except (TypeError, ValueError):

        raise ValueError(
            f"Invalid monetary value: {value}"
        )


def normalize_transactions(
    df,
    mapping: ColumnMapping,
):
    transactions = []

    for index, row in df.iterrows():

        date_value = get_value(
            row,
            mapping.date,
        )

        description_value = get_value(
            row,
            mapping.description,
        )

        if pd.isna(date_value):
            date_value = ""

        if pd.isna(description_value):
            description_value = ""

        description = str(
            description_value
        ).strip()

        transaction = Transaction(
            date=str(
                date_value
            ).strip(),

            description=description,

            debit=to_float(
                get_value(
                    row,
                    mapping.debit,
                )
            ),

            credit=to_float(
                get_value(
                    row,
                    mapping.credit,
                )
            ),

            balance=to_float(
                get_value(
                    row,
                    mapping.balance,
                )
            ),
            external_transaction_id=extract_transaction_reference(description),
            source_row_number=(int(index) + 1 if isinstance(index, Integral) else None),
        )

        transactions.append(
            transaction
        )

    return transactions