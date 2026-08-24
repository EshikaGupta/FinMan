from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent.service import (
    ask_finance_agent,
)
from .analysis.service import analyze_statement
from .database import (
    create_tables,
    get_transactions,
    save_statement,
    save_transactions,
)
from .ingestion.spreadsheet import (
    get_sample_rows,
    read_statement,
)
from .llm import (
    answer_statement_question,
    generate_financial_insights,
    map_statement_columns,
    validate_column_mapping,
)
from .pii.service import (
    PIIService,
    PIISecurityError,
)
from .pii.spreadsheet import sanitize_dataframe
from .transaction_parser import normalize_transactions
from .transaction_validator import (
    TransactionValidationError,
    validate_transactions,
)
from .analysis.intelligence import (
    categorize_transactions,
)


app = FastAPI(
    title="Finance AI API",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/statements/upload")
async def upload_statement(
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    try:
        contents = await file.read()

        # 1. Spreadsheet -> transaction table
        df = read_statement(
            file.filename,
            contents,
        )

        # 2. PII sanitization
        pii_service = PIIService()
        safe_df = sanitize_dataframe(
            df,
            pii_service,
        )

        # 3. Semantic column mapping
        mapping = map_statement_columns(
            columns=list(safe_df.columns),
            sample_rows=get_sample_rows(
                safe_df
            ),
        )

        mapping = validate_column_mapping(
            mapping,
            list(safe_df.columns),
        )

        # 4. Canonical transaction objects
        transactions = normalize_transactions(
            safe_df,
            mapping,
        )

        transactions = validate_transactions(
            transactions
        )

        # 5. Transaction intelligence
        #    - deterministic fallback
        #    - batched Gemini categorization
        #    - merchant extraction
        #    - confidence
        #    - summary
        #    - AUTOPAY subscription flag
        transactions = categorize_transactions(
            transactions
        )

        # 6. Persist before running DB-backed analysis.
        statement_id = save_statement(
            file.filename
        )

        save_transactions(
            statement_id,
            transactions,
        )

        # 7. One analysis service is now the single source
        #    of truth for dashboard metrics.
        analysis = analyze_statement(
            statement_id
        )

        insights = generate_financial_insights(
            analysis
        )

        return {
            "statement_id": statement_id,
            "filename": file.filename,
            "transaction_count": len(
                transactions
            ),
            "mapping": mapping,
            "transactions": transactions,
            "analysis": analysis,
            "insights": insights,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except PIISecurityError:
        raise HTTPException(
            status_code=500,
            detail=(
                "The statement could not be "
                "safely sanitized."
            ),
        )

    except TransactionValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/statements/{statement_id}/analysis")
async def get_statement_analysis(
    statement_id: int,
):
    try:
        return analyze_statement(
            statement_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


# @app.post("/statements/{statement_id}/ask")
# async def ask_statement_question(
#     statement_id: int,
#     question: str,
# ):
#     if not question.strip():
#         raise HTTPException(
#             status_code=400,
#             detail="Question cannot be empty.",
#         )

#     try:
#         transactions = get_transactions(
#             statement_id
#         )

#         if not transactions:
#             raise HTTPException(
#                 status_code=404,
#                 detail=(
#                     "No transactions found "
#                     "for this statement."
#                 ),
#             )

#         answer = answer_statement_question(
#             question=question,
#             transactions=transactions,
#         )

#         return {
#             "statement_id": statement_id,
#             "question": question,
#             "answer": answer,
#         }

#     except HTTPException:
#         raise

#     except Exception as exc:
#         import traceback

#         traceback.print_exc()

#         raise HTTPException(
#             status_code=500,
#             detail=str(exc),
#         )

class ChatRequest(BaseModel):
    statement_id: int
    message: str

@app.post("/chat")
async def chat(
    request: ChatRequest,
):

    try:

        answer = ask_finance_agent(
            statement_id=request.statement_id,
            question=request.message,
        )

        return {
            "statement_id": request.statement_id,
            "message": request.message,
            "answer": answer,
        }

    except Exception as exc:

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )