import io

import pandas as pd


SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
}


# ============================================================
# Local account metadata extraction
# ============================================================

_ACCOUNT_LABELS = {
    "account_number": (
        "account number", "account no", "account no.", "a/c no",
        "a/c no.", "a/c number", "ac no", "ac no.", "account #",
    ),
    "account_holder": (
        "account holder", "account name", "customer name",
        "name of account holder", "name",
    ),
    "account_type": (
        "account type", "a/c type", "ac type",
    ),
    "bank_name": (
        "bank name", "bank",
    ),
    "ifsc": (
        "ifsc", "ifsc code",
    ),
}


def _clean_metadata_value(value):
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\n", " ").split()).strip()


def _normalize_metadata_label(value):
    value = _clean_metadata_value(value).lower()
    return value.replace(":", "").strip()


def _looks_like_account_number(value):
    value = _clean_metadata_value(value)
    if not value:
        return False
    compact = value.replace(" ", "").replace("-", "")
    return bool(__import__("re").fullmatch(r"[A-Za-z0-9]{6,24}", compact))


def extract_account_details(df):
    """Extract account metadata locally from the statement header.

    This function runs on the raw spreadsheet dataframe and must be called
    before PII sanitization or any Gemini request. It intentionally returns
    only metadata; it is never passed to the LLM.
    """
    result = {
        "account_holder": "",
        "account_number": "",
        "account_type": "",
        "bank_name": "",
        "ifsc": "",
    }

    header_info = detect_transaction_header(df)
    stop_row = header_info["row_index"] if header_info else min(len(df), 80)
    search_df = df.iloc[:stop_row]

    import re

    for row_index in range(len(search_df)):
        row = search_df.iloc[row_index].tolist()
        for col_index, cell in enumerate(row):
            raw_cell = _clean_metadata_value(cell)
            label = _normalize_metadata_label(cell)
            if not label:
                continue

            # Handle inline forms such as:
            #   Account Number: 1234567890
            #   IFSC: HDFC0001234
            for field, aliases in _ACCOUNT_LABELS.items():
                if result[field]:
                    continue
                for alias in aliases:
                    prefix = alias + ":"
                    if label.startswith(prefix):
                        inline_value = raw_cell[len(prefix):].strip()
                        if inline_value and (
                            field != "account_number"
                            or _looks_like_account_number(inline_value)
                        ):
                            result[field] = inline_value
                            break
                if result[field]:
                    break

            if label in {alias for aliases in _ACCOUNT_LABELS.values() for alias in aliases}:
                matched_field = next(
                    (field for field, aliases in _ACCOUNT_LABELS.items() if label in aliases),
                    None,
                )
            else:
                matched_field = None

            if not matched_field or result[matched_field]:
                continue

            candidates = []
            if col_index + 1 < len(row):
                candidates.append(row[col_index + 1])
            if col_index + 2 < len(row):
                candidates.append(row[col_index + 2])

            for candidate in candidates:
                value = _clean_metadata_value(candidate)
                if not value:
                    continue
                if matched_field == "account_number" and not _looks_like_account_number(value):
                    continue
                result[matched_field] = value
                break

    # Some statements put metadata in a two-column label/value arrangement
    # but omit a recognizable label. Look for a likely account number only
    # in the pre-transaction header region as a final local fallback.
    if not result["account_number"]:
        import re
        for row_index in range(len(search_df)):
            for cell in search_df.iloc[row_index].tolist():
                value = _clean_metadata_value(cell)
                compact = value.replace(" ", "").replace("-", "")
                if re.fullmatch(r"\d{8,18}", compact):
                    result["account_number"] = value
                    break
            if result["account_number"]:
                break

    return result


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
    extract_transactions=True,
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

    if not extract_transactions:
        return df

    return extract_transaction_table(df)


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
    Footer/note rows after the transaction table are also ignored.

    A valid transaction row must contain a parseable date in
    the detected date column.
    """

    header_info = detect_transaction_header(df)

    if header_info is None:
        raise ValueError(
            "Could not find the transaction table."
        )

    header_row = header_info["row_index"]
    date_column_index = header_info["columns"]["date"]

    # --------------------------------------------------------
    # Read the actual header values
    # --------------------------------------------------------

    headers = []

    for value in df.iloc[header_row]:

        if pd.isna(value):
            headers.append("")

        else:
            headers.append(
                str(value).strip()
            )

    # --------------------------------------------------------
    # Extract everything below the transaction header
    # --------------------------------------------------------

    transactions = df.iloc[
        header_row + 1:
    ].copy()

    transactions.columns = headers

    # --------------------------------------------------------
    # Remove completely empty rows
    # --------------------------------------------------------

    transactions = transactions.dropna(
        how="all"
    )

    # --------------------------------------------------------
    # Remove completely empty columns
    # --------------------------------------------------------

    transactions = transactions.dropna(
        axis=1,
        how="all"
    )

    transactions = transactions.reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Remove footer rows
    #
    # Bank statements commonly contain things like:
    #
    # Note | ...
    # Total | ...
    # Statement Summary | ...
    #
    # after the actual transactions.
    #
    # The transaction date column gives us a reliable way
    # to distinguish transaction rows from these footers.
    # --------------------------------------------------------

    date_column = headers[date_column_index]

    if date_column not in transactions.columns:
        raise ValueError(
            "Transaction date column could not be found."
        )

    parsed_dates = pd.to_datetime(
        transactions[date_column],
        errors="coerce",
        dayfirst=True,
    )

    valid_date_rows = parsed_dates.notna()

    # Find the first non-date row after transactions begin.
    #
    # Since transaction tables are contiguous, everything after
    # the first invalid date is treated as footer content.
    invalid_positions = (
        valid_date_rows[~valid_date_rows].index
    )

    if len(invalid_positions) > 0:

        first_invalid_position = (
            invalid_positions[0]
        )

        transactions = transactions.iloc[
            :first_invalid_position
        ].copy()

    # --------------------------------------------------------
    # Final cleanup
    # --------------------------------------------------------

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