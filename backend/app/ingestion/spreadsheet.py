import io

import pandas as pd


SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
}


# ============================================================
# Transaction column aliases
# ============================================================

TRANSACTION_COLUMN_ALIASES = {
    "date": {
        "date",
        "txn date",
        "transaction date",
        "transaction dt",
        "txn dt",
    },

    "description": {
        "narration",
        "description",
        "transaction description",
        "transaction details",
        "transaction detail",
        "particulars",
        "remarks",
    },

    "debit": {
        "withdrawal",
        "withdrawals",
        "withdrawal amt",
        "withdrawal amt.",
        "debit",
        "debit amount",
        "debit amt",
        "debit amt.",
    },

    "credit": {
        "deposit",
        "deposits",
        "deposit amt",
        "deposit amt.",
        "credit",
        "credit amount",
        "credit amt",
        "credit amt.",
    },

    "balance": {
        "balance",
        "closing balance",
        "closing bal",
        "available balance",
        "running balance",
    },
}


# ============================================================
# File reading
# ============================================================

def read_statement(
    filename,
    content,
):
    """
    Read a CSV/XLSX bank statement and extract
    the transaction table.

    The statement may contain account metadata
    before the transaction table.
    """

    extension = (
        "."
        + filename.lower().split(".")[-1]
    )

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Only CSV and XLSX files are supported."
        )

    buffer = io.BytesIO(content)

    if extension == ".csv":

        df = pd.read_csv(
            buffer,
            header=None,
        )

    else:

        df = pd.read_excel(
            buffer,
            header=None,
            engine="openpyxl",
        )

    return extract_transaction_table(
        df
    )


# ============================================================
# Header normalization
# ============================================================

def normalize_header(
    value,
):
    """
    Normalize a possible transaction header
    for comparison.

    Example:

        "Txn Date"       -> "txn date"
        "Closing Balance" -> "closing balance"
    """

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace("\n", " ")
        .replace("\r", " ")
    )


# ============================================================
# Transaction header detection
# ============================================================

def detect_transaction_header(
    df,
):
    """
    Find the row containing the transaction
    table header.

    The detector supports common variations
    such as:

        Date
        Txn Date
        Transaction Date

    and:

        Narration
        Description
        Particulars

    Returns:

        {
            "row_index": int,
            "columns": {
                "date": column_index,
                "description": column_index,
                "debit": column_index,
                "credit": column_index,
                "balance": column_index
            }
        }

    Returns None if no transaction header
    can be identified.
    """

    for row_index in range(
        len(df)
    ):

        row = df.iloc[
            row_index
        ]

        detected = {}

        for column_index, value in (
            row.items()
        ):

            normalized = (
                normalize_header(value)
            )

            if not normalized:
                continue

            for (
                field,
                aliases,
            ) in TRANSACTION_COLUMN_ALIASES.items():

                if normalized in aliases:

                    detected[field] = (
                        column_index
                    )

                    break

        # A valid transaction table should
        # contain at least:
        #
        # date
        # description
        #
        # and at least one amount column.

        has_required_columns = (
            "date" in detected
            and "description" in detected
            and (
                "debit" in detected
                or "credit" in detected
            )
        )

        if has_required_columns:

            return {
                "row_index": row_index,
                "columns": detected,
            }

    return None


# ============================================================
# Transaction table extraction
# ============================================================

def extract_transaction_table(
    df,
):
    """
    Extract the transaction rows from a statement.

    Metadata above the transaction table is ignored.

    Original column names are preserved because
    Gemini will perform the final semantic mapping.
    """

    header_info = (
        detect_transaction_header(df)
    )

    if header_info is None:

        raise ValueError(
            "Could not find the transaction table."
        )

    header_row = (
        header_info["row_index"]
    )

    # Read the actual header values
    # from the detected row.
    headers = []

    for value in df.iloc[
        header_row
    ]:

        if pd.isna(value):
            headers.append("")
        else:
            headers.append(
                str(value).strip()
            )

    # Extract everything below
    # the transaction header.
    transactions = df.iloc[
        header_row + 1:
    ].copy()

    transactions.columns = headers

    # Remove completely empty rows.
    transactions = transactions.dropna(
        how="all"
    )

    # Remove completely empty columns.
    transactions = transactions.dropna(
        axis=1,
        how="all"
    )

    transactions = transactions.reset_index(
        drop=True
    )

    return transactions


# ============================================================
# Preview helper
# ============================================================

def get_sample_rows(
    df,
    limit=10,
):
    """
    Return a small JSON-friendly preview
    of the extracted transaction table.
    """

    return df.head(
        limit
    ).to_dict(
        orient="records"
    )