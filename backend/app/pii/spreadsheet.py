import pandas as pd
from .narration import (
    sanitize_narration,
)
from .service import PIIService

NARRATION_COLUMNS = {
    "narration",
    "description",
    "transaction details",
    "transaction detail",
    "particulars",
    "remarks",
    "transaction particulars",
    "transaction description",
}

def is_narration_column(
    column_name,
):

    normalized = (
        str(column_name)
        .strip()
        .lower()
    )

    return normalized in NARRATION_COLUMNS

def sanitize_dataframe(
    df,
    pii_service,
):

    safe_df = df.copy()

    for column in safe_df.columns:

        if is_narration_column(column):

            for index in safe_df.index:

                value = safe_df.at[
                    index,
                    column,
                ]

                if pd.isna(value):
                    continue

                safe_df.at[
                    index,
                    column,
                ] = sanitize_narration(
                    value
                )

            continue

        for index in safe_df.index:

            value = safe_df.at[
                index,
                column,
            ]

            if pd.isna(value):
                continue

            result = pii_service.sanitize(
                str(value)
            )

            safe_df.at[
                index,
                column,
            ] = result.text

    return safe_df