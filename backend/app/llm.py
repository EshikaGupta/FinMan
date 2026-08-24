from google import genai
from google.genai import types
import json
from .config import settings
from .schemas import ColumnMapping


client = genai.Client(
    api_key=settings.gemini_api_key
)

def answer_statement_question(
    question,
    transactions,
):
    """
    Answer a user's question using only the
    transactions belonging to one statement.
    """

    transaction_lines = []

    for index, transaction in enumerate(
        transactions,
        start=1,
    ):
        transaction_lines.append(
            f"""
Transaction {index}:
Date: {transaction.date}
Description: {transaction.description}
Debit: {transaction.debit}
Credit: {transaction.credit}
Balance: {transaction.balance}
"""
        )

    transaction_context = "\n".join(
        transaction_lines
    )

    prompt = f"""
You are a personal finance assistant.

Answer the user's question using ONLY the
bank transactions provided below.

Do not invent transactions, amounts,
merchants, dates, or financial information.

If the information cannot be determined
from the transactions, clearly say so.

Keep the answer concise and easy to understand.

User question:
{question}

Bank transactions:
{transaction_context}
"""

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
    )

    return response.text.strip()
    
def generate_financial_insights(
    analysis,
):
    """
    Generate human-readable financial insights
    from already-calculated and sanitized data.

    Gemini does NOT calculate the financial numbers.
    """

    prompt = f"""
You are a personal finance analysis assistant.

Analyze the following financial summary.

IMPORTANT RULES:

1. Do not invent any numbers.
2. Use only the information provided.
3. Do not recalculate totals unless necessary.
4. Do not mention or infer private identifiers.
5. Do not identify a person from transaction names.
6. Give practical, concise observations.
7. Do not give investment or financial advice.
8. If there is not enough information for an observation,
   simply don't make that observation.

Financial summary:

{json.dumps(analysis, indent=2)}

Return ONLY valid JSON in this exact structure:

{{
    "summary": "2-3 sentence overall summary",
    "spending_observations": [
        "observation 1",
        "observation 2"
    ],
    "category_observations": [
        "observation 1",
        "observation 2"
    ],
    "positive_observations": [
        "observation 1",
        "observation 2"
    ],
    "areas_to_watch": [
        "observation 1",
        "observation 2"
    ]
}}
"""

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
    )

    text = response.text.strip()

    # Gemini sometimes wraps JSON in markdown.
    if text.startswith("```"):

        text = text.replace(
            "```json",
            "",
        )

        text = text.replace(
            "```",
            "",
        )

        text = text.strip()

    try:

        return json.loads(text)

    except json.JSONDecodeError:

        return {
            "summary": text,
            "spending_observations": [],
            "category_observations": [],
            "positive_observations": [],
            "areas_to_watch": [],
        }

def map_statement_columns(
    columns,
    sample_rows,
):
    prompt = f"""
You are analyzing a bank statement spreadsheet.

Identify which spreadsheet columns correspond to
the following canonical financial fields:

- date
- description
- debit
- credit
- balance

Spreadsheet columns:
{columns}

Sample transaction rows:
{sample_rows}

Rules:

1. Use the exact spreadsheet column names.
2. Never invent a column name.
3. If debit, credit, or balance does not exist,
   return null.
4. The description column should contain the
   transaction narration or transaction details.
5. Do not interpret transaction values.
6. Do not modify any transaction data.

Return the column mapping.
"""

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ColumnMapping,
        ),
    )

    if not response.text:
        raise ValueError(
            "Gemini returned an empty column mapping."
        )

    return ColumnMapping.model_validate_json(
        response.text
    )


def validate_column_mapping(
    mapping,
    columns,
):
    available = set(columns)

    required = [
        mapping.date,
        mapping.description,
    ]

    for column in required:

        if column not in available:
            raise ValueError(
                f"Invalid column mapping: {column}"
            )

    optional = [
        mapping.debit,
        mapping.credit,
        mapping.balance,
    ]

    for column in optional:

        if (
            column is not None
            and column not in available
        ):
            raise ValueError(
                f"Invalid column mapping: {column}"
            )

    return mapping