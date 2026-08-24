import json
from typing import List

from google import genai
from google.genai import types

from ..config import settings
from ..schemas import (
    CategorizationBatch,
    Transaction,
)

from .categorizer import (
    categorize_transaction,
    detect_merchant,
    is_autopay,
)


client = genai.Client(
    api_key=settings.gemini_api_key
)


BATCH_SIZE = 50


VALID_CATEGORIES = {
    "Food",
    "Transport",
    "Shopping",
    "Entertainment",
    "Bills & Utilities",
    "Investments",
    "Salary",
    "Refund",
    "Cash Withdrawal",
    "Other",
}


FALLBACK_CONFIDENCE = 0.50


def _fallback(
    transaction: Transaction,
) -> None:
    """
    Populate deterministic intelligence.

    This guarantees that the application still works
    if Gemini is unavailable.
    """

    transaction.category = (
        categorize_transaction(
            transaction.description
        )
    )

    transaction.merchant = (
        detect_merchant(
            transaction.description
        )
        or ""
    )

    transaction.confidence = (
        FALLBACK_CONFIDENCE
    )

    transaction.summary = (
        f"{transaction.merchant} transaction"
        if transaction.merchant
        else transaction.description[:60]
    )

    transaction.is_subscription = (
        is_autopay(
            transaction.description
        )
    )


def _amount_and_type(
    transaction: Transaction,
):
    if (
        transaction.debit is not None
        and transaction.debit > 0
    ):
        return (
            "debit",
            transaction.debit,
        )

    if (
        transaction.credit is not None
        and transaction.credit > 0
    ):
        return (
            "credit",
            transaction.credit,
        )

    return (
        "unknown",
        0,
    )


def _categorize_batch(
    transactions: List[Transaction],
):
    rows = []

    for index, transaction in enumerate(
        transactions
    ):

        txn_type, amount = (
            _amount_and_type(
                transaction
            )
        )

        rows.append(
            {
                "id": str(index),
                "type": txn_type,
                "amount": amount,
                "description": (
                    transaction.description
                ),
            }
        )

    prompt = f"""
You are a transaction categorization engine
for a personal finance application.

Categorize every transaction below.

The descriptions have already been
privacy-sanitized.

Do not try to reconstruct redacted
identifiers.

Allowed categories:

{json.dumps(
    sorted(VALID_CATEGORIES)
)}

For every transaction return:

- id: exact input id
- category: one allowed category
- merchant: short normalized merchant/payee name
- confidence: number from 0.0 to 1.0
- summary: 2-6 words describing the transaction

Rules:

1. Use the FULL narration.

2. Preserve recognizable merchants such as
   Swiggy, Zomato, Uber, Amazon, Netflix,
   Spotify, etc.

3. Preserve recognizable person/payee names
   when they are present in the narration.

4. Salary deposits should be Salary.

5. Refunds should be Refund.

6. AUTOPAY transactions may indicate
   subscriptions.

7. Bank transfers clearly moving money
   between the user's own accounts should
   normally be Other.

8. Do not invent a merchant.

9. Do not expose or reconstruct redacted
   PII.

10. Do not return categories outside the
    allowed list.

Transactions:

{json.dumps(
    rows,
    ensure_ascii=False
)}
"""

    response = (
        client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=(
                    CategorizationBatch
                ),
            ),
        )
    )

    if not response.text:
        raise ValueError(
            "Gemini returned an empty "
            "categorization response."
        )

    return (
        CategorizationBatch
        .model_validate_json(
            response.text
        )
        .results
    )


def categorize_transactions(
    transactions: List[Transaction],
) -> List[Transaction]:
    """
    Add merchant/category/summary/confidence
    to every transaction.

    Flow:

        Transaction
             ↓
        deterministic extraction
             ↓
        Gemini categorization
             ↓
        deterministic merchant protection
             ↓
        AUTOPAY detection
    """

    # -----------------------------------------------------
    # STEP 1
    # Always prepare deterministic fallback data first.
    # -----------------------------------------------------

    for transaction in transactions:
        _fallback(transaction)

    # -----------------------------------------------------
    # STEP 2
    # Gemini categorization in batches.
    # -----------------------------------------------------

    for start in range(
        0,
        len(transactions),
        BATCH_SIZE,
    ):

        batch = transactions[
            start : start + BATCH_SIZE
        ]

        try:

            results = _categorize_batch(
                batch
            )

            for result in results:

                try:
                    index = int(
                        result.id
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if (
                    index < 0
                    or index >= len(batch)
                ):
                    continue

                transaction = batch[
                    index
                ]

                # -------------------------------------------------
                # CATEGORY
                #
                # Gemini is the primary category engine.
                # -------------------------------------------------

                if (
                    result.category
                    in VALID_CATEGORIES
                ):

                    transaction.category = (
                        result.category
                    )

                # -------------------------------------------------
                # MERCHANT
                #
                # IMPORTANT:
                #
                # If we already extracted a merchant from the
                # narration, keep it.
                #
                # Gemini is only allowed to provide a merchant
                # when deterministic extraction found nothing.
                # -------------------------------------------------

                deterministic_merchant = (
                    detect_merchant(
                        transaction.description
                    )
                )

                if deterministic_merchant:

                    transaction.merchant = (
                        deterministic_merchant
                    )

                elif result.merchant.strip():

                    transaction.merchant = (
                        result.merchant.strip()
                    )

                # -------------------------------------------------
                # CONFIDENCE
                # -------------------------------------------------

                transaction.confidence = max(
                    0.0,
                    min(
                        1.0,
                        float(
                            result.confidence
                        ),
                    ),
                )

                # -------------------------------------------------
                # SUMMARY
                # -------------------------------------------------

                if result.summary.strip():

                    transaction.summary = (
                        result.summary.strip()
                    )

        except Exception:
            # Deterministic fallback remains intact.
            pass

        # ---------------------------------------------------------
        # STEP 3
        # AUTOPAY is deterministic.
        # ---------------------------------------------------------

        for transaction in batch:

            transaction.is_subscription = (
                is_autopay(
                    transaction.description
                )
            )

    return transactions