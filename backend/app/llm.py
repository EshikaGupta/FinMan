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
    Generate human-readable financial insights from already-calculated,
    account-scoped and privacy-sanitized aggregates.

    Gemini does not calculate or invent the underlying financial numbers.
    """

    prompt = f"""
You are a personal finance analysis assistant.

Analyze the following financial summary and identify useful, evidence-based
patterns in the user's financial activity.

IMPORTANT RULES:

1. Do not invent any numbers, transactions, merchants, categories, or patterns.
2. Use ONLY the information provided in the financial summary.
3. Do not recalculate totals unless necessary to explain an observation.
4. Do not mention, expose, reconstruct, or infer private identifiers such as:
   - account numbers
   - IFSC codes
   - account holder names
   - phone numbers
   - email addresses
   - addresses
5. Do not identify a person from transaction descriptions, merchant names,
   narrations, or other transaction data.
6. Do not make assumptions about the user's lifestyle, intentions, income source,
   relationships, or personal circumstances.
7. Do not give investment, tax, lending, insurance, or financial advice.
8. Do not tell the user what they should invest in, buy, sell, cancel, or do
   financially.
9. Only make an observation when the supplied data provides enough evidence.
10. If a section cannot be meaningfully analyzed from the available data,
    return an empty array for that section.
11. Keep observations practical, concise, and specific.
12. Avoid generic advice such as "spend less" or "save more" unless the data
    provides a specific pattern that supports the observation.
13. Distinguish between facts and interpretations. Do not present an inference
    as a fact.
14. Do not treat every large transaction as unnecessary. Only flag potentially
    unusual or discretionary spending when the available data supports it.
15. Do not assume that a recurring transaction is a subscription unless the
    financial summary identifies it as such.
16. Do not assume that a transaction is an investment unless the financial
    summary categorizes or identifies it as an investment.
17. Do not assume that an expense is unnecessary. Use wording such as
    "potentially discretionary" or "worth reviewing" when appropriate.
18. Do not recommend cancelling subscriptions. You may point out notable
    recurring costs or patterns.
19. Do not recommend investments or judge whether an investment is good or bad.
20. Do not repeat the same observation across multiple sections.
21. The financial summary may contain merchant names. Use them only when useful
    for describing a spending pattern; never use them to identify a person.
22. Never reveal the internal account_id or statement_id fields.

ANALYSIS AREAS:

A. OVERALL FINANCIAL PICTURE
- Summarize the overall financial position represented by the data.
- Mention income, spending, savings rate, and cash flow only when present.
- Highlight the most important overall pattern.

B. SPENDING PATTERNS
Look for evidence of:
- unusually high spending
- periods with higher/lower spending
- concentration of spending
- frequent spending
- large individual expenses
- changes in spending over time
- recurring vs non-recurring spending when identifiable
- notable spending patterns that may deserve attention

C. CATEGORY ANALYSIS
Look for:
- largest spending categories
- categories that dominate spending
- categories with notable changes
- categories with meaningful frequency or concentration
- potentially discretionary categories

D. SUBSCRIPTIONS & RECURRING EXPENSES
If subscription information is available:
- identify notable subscriptions
- identify recurring expense concentration
- identify subscriptions that represent meaningful recurring costs
- identify changes in recurring expenses
- identify patterns that may be worth reviewing

E. POTENTIALLY DISCRETIONARY / UNNECESSARY EXPENSES
Use the supplied potentially_discretionary_spending data when available.
- Identify categories with notable potentially discretionary spending.
- Do NOT call these expenses unnecessary unless the data explicitly supports it.
- Use cautious wording such as "potentially discretionary" or "worth reviewing".

F. INVESTMENTS & INVESTMENT-LIKE ACTIVITY
If investment_activity is available:
- summarize investment activity using only supplied figures
- identify frequency or changes in investment activity
- compare investment activity with other supplied financial metrics only when
  directly supported
- do not recommend, evaluate, or criticize investments
- do not infer investment goals

G. INCOME
If income information is available:
- identify major income patterns
- identify recurring income where explicitly indicated
- identify changes or concentration in income categories when supported
- mention salary income separately when explicitly provided

H. CASH FLOW & SAVINGS
If cash-flow or savings information is available:
- identify positive or negative cash-flow patterns
- identify periods with notable changes
- mention savings rate when explicitly provided
- identify whether spending is above/below income when directly supported

I. MERCHANT & TRANSACTION PATTERNS
If merchant-level information is available:
- identify repeated or concentrated spending
- identify merchants with meaningful spending
- identify recurring patterns
- do not identify people from names in transaction data

J. POSITIVE FINANCIAL PATTERNS
Identify evidence-based positives such as:
- positive net cash flow
- positive savings rate
- stable or recurring income
- declining spending in a category
- reduced discretionary spending
- consistent investment activity, if explicitly identified
- other clearly supported positive trends

K. AREAS TO WATCH
Identify evidence-based areas that may deserve attention, such as:
- increasing spending
- high category concentration
- recurring expenses
- potentially discretionary spending
- negative cash flow
- declining savings rate
- unusual spending spikes
- increased subscription costs
- significant income changes

These are observations, not financial advice.

IMPORTANT:
Do not force every section to contain observations.
If the available information does not support a meaningful observation,
return an empty array.

Financial summary:

{json.dumps(analysis, indent=2, ensure_ascii=False, default=str)}

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
    "subscription_observations": [
        "observation 1",
        "observation 2"
    ],
    "investment_observations": [
        "observation 1",
        "observation 2"
    ],
    "income_observations": [
        "observation 1",
        "observation 2"
    ],
    "cash_flow_observations": [
        "observation 1",
        "observation 2"
    ],
    "discretionary_spending_observations": [
        "observation 1",
        "observation 2"
    ],
    "merchant_observations": [
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
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    text = (response.text or "").strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    fallback = {
        "summary": text,
        "spending_observations": [],
        "category_observations": [],
        "subscription_observations": [],
        "investment_observations": [],
        "income_observations": [],
        "cash_flow_observations": [],
        "discretionary_spending_observations": [],
        "merchant_observations": [],
        "positive_observations": [],
        "areas_to_watch": [],
    }

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return fallback

    # Normalize the response so the frontend can rely on every key existing.
    for key, default in fallback.items():
        if key not in parsed:
            parsed[key] = default

    return parsed

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