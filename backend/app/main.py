import sqlite3

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import get_current_user
from .agent.service import ask_finance_agent
from .analysis.service import analyze_account, analyze_statement
from .database import (
    create_tables,
    get_account,
    get_accounts,
    get_account_statements,
    get_account_transactions,
    get_statement,
    get_statement_by_hash,
    get_statement_by_fingerprint,
    get_import_by_fingerprint,
    get_transactions,
    save_import_log,
    save_statement,
    save_transactions,
    upsert_account,
)
from .ingestion.spreadsheet import (
    extract_account_details,
    get_sample_rows,
    read_statement,
)
from .llm import (
    generate_financial_insights,
    map_statement_columns,
    validate_column_mapping,
)
from .pii.service import PIIService, PIISecurityError
from .pii.spreadsheet import sanitize_dataframe
from .transaction_parser import normalize_transactions
from .transaction_validator import TransactionValidationError, validate_transactions
from .services.imports import build_statement_identity, get_file_hash, get_file_format
from .analysis.intelligence import categorize_transactions
from .config import settings


app = FastAPI(title="Finance AI API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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


@app.get("/auth/me")
async def auth_me(request: Request, user=Depends(get_current_user)):
    return {"user": user}


@app.get("/accounts")
async def list_accounts(user=Depends(get_current_user)):
    return {"accounts": get_accounts(user["id"])}


@app.get("/accounts/{account_id}")
async def account_details(account_id: int, user=Depends(get_current_user)):
    account = get_account(account_id, user["id"])
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    return account


@app.get("/accounts/{account_id}/analysis")
async def get_account_analysis(account_id: int, user=Depends(get_current_user)):
    account = get_account(account_id, user["id"])
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    analysis = analyze_account(account_id)
    transactions = get_account_transactions(account_id)
    return {
        "account": account,
        "analysis": analysis,
        "transactions": [t.model_dump() for t in transactions],
        "statements": get_account_statements(account_id),
    }


@app.get("/accounts/{account_id}/insights")
async def get_account_insights(account_id: int, user=Depends(get_current_user)):
    """Generate AI insights separately so dashboard loading never waits on Gemini."""
    account = get_account(account_id, user["id"])
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    analysis = analyze_account(account_id)
    insights = generate_financial_insights(analysis)
    return {"account_id": account_id, "insights": insights}


@app.get("/statements/{statement_id}/analysis")
async def get_statement_analysis(statement_id: int, user=Depends(get_current_user)):
    statement = get_statement(statement_id)
    if not statement or not statement.get("account_id") or not get_account(statement["account_id"], user["id"]):
        raise HTTPException(status_code=404, detail="Statement not found.")
    try:
        return analyze_statement(statement_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/statements/upload")
async def upload_statement(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    try:
        contents = await file.read()
        # Level 1 identity: exact uploaded bytes. Filename and file metadata
        # are intentionally excluded.
        hash_id = get_file_hash(contents)

        # IMPORTANT PRIVACY BOUNDARY:
        # Account metadata is extracted from the raw statement locally.
        # It is never passed to sanitize_dataframe, Gemini, or the agent.
        raw_df = read_statement(file.filename, contents, extract_transactions=False)
        account_details = extract_account_details(raw_df)

        if not account_details.get("account_number"):
            raise ValueError(
                "Could not find an account number in the statement header. "
                "The statement cannot be associated with an account automatically."
            )

        # Establish the account locally before checking whether this exact
        # statement has already been imported. The hash is calculated from
        # the complete uploaded file bytes, never from the filename.
        account_id = upsert_account(account_details, user["id"])
        existing_statement = get_statement_by_hash(account_id, hash_id)
        if existing_statement:
            import_log_id = save_import_log(
                user_id=user["id"],
                account_id=account_id,
                filename=file.filename,
                file_hash=hash_id,
                statement_fingerprint=None,
                file_format=get_file_format(file.filename),
                transaction_count=None,
                total_debit=None,
                total_credit=None,
                status="DUPLICATE_FILE",
                statement_id=existing_statement["id"],
            )
            return JSONResponse(
                status_code=409,
                content={
                    "detail": {
                        "code": "STATEMENT_ALREADY_EXISTS",
                        "message": "This exact file has already been imported.",
                        "reason": "LEVEL_1_FILE_IDENTITY",
                        "statement_id": existing_statement["id"],
                        "account_id": account_id,
                        "filename": existing_statement["filename"],
                        "created_at": existing_statement["created_at"],
                        "import_log_id": import_log_id,
                    }
                },
            )

        # Only the transaction table enters the AI pipeline.
        df = read_statement(file.filename, contents)
        pii_service = PIIService()
        safe_df = sanitize_dataframe(df, pii_service)

        mapping = map_statement_columns(
            columns=list(safe_df.columns),
            sample_rows=get_sample_rows(safe_df),
        )
        mapping = validate_column_mapping(mapping, list(safe_df.columns))

        transactions = normalize_transactions(safe_df, mapping)
        transactions = validate_transactions(transactions)
        transactions = categorize_transactions(transactions)

        # Level 2 identity: the financial contents of the extracted statement.
        # This deliberately ignores filename/upload metadata, so the same
        # statement exported again under a different filename is still detected.
        statement_identity = build_statement_identity(account_id, transactions)
        statement_fingerprint = statement_identity["fingerprint"]

        # ImportLog is the audit trail for every import decision. It is also
        # used as a second source for Level 2 duplicate detection, so the
        # identity is not tied only to the statements table.
        existing_financial_import = get_import_by_fingerprint(
            account_id,
            statement_fingerprint,
        )
        existing_statement = (
            get_statement_by_fingerprint(account_id, statement_fingerprint)
            or existing_financial_import
        )

        if existing_statement:
            import_log_id = save_import_log(
                user_id=user["id"],
                account_id=account_id,
                filename=file.filename,
                file_hash=hash_id,
                statement_fingerprint=statement_fingerprint,
                file_format=get_file_format(file.filename),
                transaction_count=statement_identity["transaction_count"],
                total_debit=statement_identity["total_debit"],
                total_credit=statement_identity["total_credit"],
                status="DUPLICATE_STATEMENT",
                statement_id=existing_statement.get("statement_id") or existing_statement.get("id"),
                new_transaction_count=0,
                duplicate_transaction_count=statement_identity["transaction_count"],
            )
            return JSONResponse(
                status_code=409,
                content={
                    "detail": {
                        "code": "STATEMENT_ALREADY_IMPORTED",
                        "message": "This appears to be the same financial statement that was already imported.",
                        "reason": "LEVEL_2_STATEMENT_IDENTITY",
                        "statement_id": existing_statement.get("statement_id") or existing_statement.get("id"),
                        "account_id": account_id,
                        "filename": existing_statement.get("filename"),
                        "import_log_id": import_log_id,
                    }
                },
            )

        # The account was established locally before the AI pipeline.
        # Persist the exact file hash with the statement so a byte-identical
        # upload can be rejected before another analysis is created.
        try:
            statement_id = save_statement(
                file.filename,
                account_id,
                hash_id,
                statement_fingerprint=statement_fingerprint,
                period_start=statement_identity["period_start"],
                period_end=statement_identity["period_end"],
                transaction_count=statement_identity["transaction_count"],
                total_debit=statement_identity["total_debit"],
                total_credit=statement_identity["total_credit"],
            )
        except sqlite3.IntegrityError:
            existing_statement = get_statement_by_hash(account_id, hash_id)
            if existing_statement:
                import_log_id = save_import_log(
                    user_id=user["id"],
                    account_id=account_id,
                    filename=file.filename,
                    file_hash=hash_id,
                    statement_fingerprint=statement_fingerprint,
                    file_format=get_file_format(file.filename),
                    transaction_count=statement_identity["transaction_count"],
                    total_debit=statement_identity["total_debit"],
                    total_credit=statement_identity["total_credit"],
                    status="DUPLICATE_FILE",
                    statement_id=existing_statement["id"],
                )
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": {
                            "code": "STATEMENT_ALREADY_EXISTS",
                            "message": "This exact file has already been imported.",
                            "reason": "LEVEL_1_FILE_IDENTITY",
                            "statement_id": existing_statement["id"],
                            "account_id": account_id,
                            "filename": existing_statement["filename"],
                            "import_log_id": import_log_id,
                        }
                    },
                )
            raise
        import_result = save_transactions(statement_id, transactions)
        import_log_id = save_import_log(
            user_id=user["id"],
            account_id=account_id,
            filename=file.filename,
            file_hash=hash_id,
            statement_fingerprint=statement_fingerprint,
            file_format=get_file_format(file.filename),
            transaction_count=statement_identity["transaction_count"],
            total_debit=statement_identity["total_debit"],
            total_credit=statement_identity["total_credit"],
            status="COMPLETED",
            statement_id=statement_id,
            new_transaction_count=import_result["new_transactions"],
            duplicate_transaction_count=import_result["duplicate_transactions"],
        )

        # Dashboard data is account-scoped, so multiple statements for the same
        # account are automatically combined.
        account = get_account(account_id)
        analysis = analyze_account(account_id)
        account_transactions = [
            t.model_dump() for t in get_account_transactions(account_id)
        ]

        return {
            "account_id": account_id,
            "statement_id": statement_id,
            "import_log_id": import_log_id,
            "filename": file.filename,
            "statement_identity": {
                "level_1_file_hash": hash_id,
                "level_2_statement_fingerprint": statement_fingerprint,
            },
            "transaction_count": len(account_transactions),
            "uploaded_transaction_count": len(transactions),
            "new_transaction_count": import_result["new_transactions"],
            "duplicate_transaction_count": import_result["duplicate_transactions"],
            "account": account,
            "account_details": account,
            "statements": get_account_statements(account_id),
            "mapping": mapping,
            "transactions": account_transactions,
            "analysis": analysis,
            # AI insights are intentionally fetched separately after the
            # dashboard is available. Upload must not wait on Gemini here.
            "insights": None,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PIISecurityError:
        raise HTTPException(status_code=500, detail="The statement could not be safely sanitized.")
    except TransactionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


class ChatRequest(BaseModel):
    account_id: int
    message: str


@app.post("/chat")
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty.")
        if not get_account(request.account_id, user["id"]):
            raise HTTPException(status_code=404, detail="Account not found.")

        answer = ask_finance_agent(
            account_id=request.account_id,
            question=request.message,
        )
        return {
            "account_id": request.account_id,
            "message": request.message,
            "answer": answer,
        }
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))