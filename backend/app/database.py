import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schemas import Transaction


DATABASE_PATH = Path("data/finance.db")


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _add_column_if_missing(cursor, table, column, definition):
    columns = {
        row["name"]
        for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def create_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                picture TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_holder TEXT,
                account_number TEXT NOT NULL UNIQUE,
                account_type TEXT,
                bank_name TEXT,
                ifsc TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS statements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL,
                account_id INTEGER,
                hash_id TEXT,
                statement_fingerprint TEXT,
                period_start TEXT,
                period_end TEXT,
                transaction_count INTEGER,
                new_transaction_count INTEGER,
                duplicate_transaction_count INTEGER,
                total_debit REAL,
                total_credit REAL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS import_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_id INTEGER,
                filename TEXT NOT NULL,
                file_hash TEXT,
                statement_fingerprint TEXT,
                format TEXT,
                transaction_count INTEGER,
                new_transaction_count INTEGER,
                duplicate_transaction_count INTEGER,
                total_debit REAL,
                total_credit REAL,
                status TEXT NOT NULL,
                statement_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (statement_id) REFERENCES statements(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_id INTEGER NOT NULL,
                account_id INTEGER,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                debit REAL,
                credit REAL,
                balance REAL,
                external_transaction_id TEXT,
                canonical_fingerprint TEXT,
                category TEXT,
                merchant TEXT,
                confidence REAL,
                summary TEXT,
                is_subscription INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (statement_id) REFERENCES statements(id),
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transaction_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                statement_id INTEGER NOT NULL,
                statement_row_number INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE (transaction_id, statement_id, statement_row_number),
                FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
                FOREIGN KEY (statement_id) REFERENCES statements(id) ON DELETE CASCADE
            )
            """
        )

        # Migration for older FinMan databases.
        _add_column_if_missing(cursor, "users", "clerk_user_id", "TEXT")
        _add_column_if_missing(cursor, "accounts", "user_id", "INTEGER")
        _add_column_if_missing(cursor, "statements", "account_id", "INTEGER")
        _add_column_if_missing(cursor, "statements", "hash_id", "TEXT")
        _add_column_if_missing(cursor, "statements", "statement_fingerprint", "TEXT")
        _add_column_if_missing(cursor, "statements", "period_start", "TEXT")
        _add_column_if_missing(cursor, "statements", "period_end", "TEXT")
        _add_column_if_missing(cursor, "statements", "transaction_count", "INTEGER")
        _add_column_if_missing(cursor, "statements", "total_debit", "REAL")
        _add_column_if_missing(cursor, "statements", "total_credit", "REAL")
        _add_column_if_missing(cursor, "import_logs", "new_transaction_count", "INTEGER")
        _add_column_if_missing(cursor, "import_logs", "duplicate_transaction_count", "INTEGER")
        _add_column_if_missing(cursor, "transactions", "account_id", "INTEGER")
        _add_column_if_missing(cursor, "transactions", "external_transaction_id", "TEXT")
        _add_column_if_missing(cursor, "transactions", "canonical_fingerprint", "TEXT")
        _add_column_if_missing(cursor, "transactions", "category", "TEXT")
        _add_column_if_missing(cursor, "transactions", "merchant", "TEXT")
        _add_column_if_missing(cursor, "transactions", "confidence", "REAL")
        _add_column_if_missing(cursor, "transactions", "summary", "TEXT")
        _add_column_if_missing(
            cursor,
            "transactions",
            "is_subscription",
            "INTEGER NOT NULL DEFAULT 0",
        )

        # Backfill account ownership and source provenance for databases that
        # existed before canonical transaction support.
        cursor.execute(
            """
            UPDATE transactions
            SET account_id = (
                SELECT account_id FROM statements
                WHERE statements.id = transactions.statement_id
            )
            WHERE account_id IS NULL
            """
        )
        cursor.execute(
            """
            INSERT OR IGNORE INTO transaction_sources (
                transaction_id, statement_id, statement_row_number, created_at
            )
            SELECT id, statement_id, id, ?
            FROM transactions
            """,
            (datetime.now(timezone.utc).isoformat(),),
        )

        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_clerk_user_id ON users(clerk_user_id) WHERE clerk_user_id IS NOT NULL"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_statements_account_id ON statements(account_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_statement_id ON transactions(statement_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_external_id ON transactions(account_id, external_transaction_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_fingerprint ON transactions(account_id, canonical_fingerprint)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transaction_sources_statement ON transaction_sources(statement_id)"
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_statements_account_hash_id
            ON statements(account_id, hash_id)
            WHERE hash_id IS NOT NULL
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_statements_account_fingerprint
            ON statements(account_id, statement_fingerprint)
            WHERE statement_fingerprint IS NOT NULL
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_import_logs_account_fingerprint
            ON import_logs(account_id, statement_fingerprint)
            WHERE statement_fingerprint IS NOT NULL
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_import_logs_file_hash
            ON import_logs(account_id, file_hash)
            WHERE file_hash IS NOT NULL
            """
        )

        connection.commit()
    finally:
        connection.close()


def get_or_create_clerk_user(clerk_user_id):
    """Return the local FinMan user for a Clerk user ID, creating it if needed."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE clerk_user_id = ?",
            (clerk_user_id,),
        )
        existing = cursor.fetchone()
        if existing:
            return get_user(existing["id"])

        # Preserve a single legacy local user's data when migrating from the
        # previous Google/session implementation. This is safe for the current
        # single-user local database and avoids orphaning existing accounts.
        cursor.execute(
            "SELECT id FROM users WHERE clerk_user_id IS NULL ORDER BY id LIMIT 1"
        )
        legacy = cursor.fetchone()
        if legacy:
            user_id = legacy["id"]
            cursor.execute(
                "UPDATE users SET clerk_user_id = ? WHERE id = ?",
                (clerk_user_id, user_id),
            )
        else:
            cursor.execute(
                "INSERT INTO users (google_sub, email, name, picture, created_at, clerk_user_id) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    clerk_user_id,
                    f"clerk:{clerk_user_id}",
                    "FinMan User",
                    None,
                    datetime.now(timezone.utc).isoformat(),
                    clerk_user_id,
                ),
            )
            user_id = cursor.lastrowid

        connection.commit()
        return get_user(user_id)
    finally:
        connection.close()


def get_user(user_id):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, clerk_user_id, email, name, picture, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "clerk_user_id": row["clerk_user_id"],
            "email": row["email"],
            "name": row["name"],
            "picture": row["picture"],
            "created_at": row["created_at"],
        }
    finally:
        connection.close()


def get_user_by_clerk_id(clerk_user_id):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, clerk_user_id, email, name, picture, created_at FROM users WHERE clerk_user_id = ?",
            (clerk_user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "clerk_user_id": row["clerk_user_id"],
            "email": row["email"],
            "name": row["name"],
            "picture": row["picture"],
            "created_at": row["created_at"],
        }
    finally:
        connection.close()

def upsert_account(account_details, user_id):
    """Create or update an account using its account number as identity."""
    account_number = str(account_details.get("account_number") or "").strip()
    if not account_number:
        raise ValueError("Account number could not be extracted from the statement.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id FROM accounts WHERE account_number = ? AND user_id = ?",
            (account_number, user_id),
        )
        existing = cursor.fetchone()

        values = (
            account_details.get("account_holder") or None,
            account_number,
            account_details.get("account_type") or None,
            account_details.get("bank_name") or None,
            account_details.get("ifsc") or None,
        )

        if existing:
            account_id = existing["id"]
            cursor.execute(
                """
                UPDATE accounts
                SET account_holder = COALESCE(?, account_holder),
                    account_type = COALESCE(?, account_type),
                    bank_name = COALESCE(?, bank_name),
                    ifsc = COALESCE(?, ifsc)
                WHERE id = ? AND user_id = ?
                """,
                (*values[:1], values[2], values[3], values[4], account_id, user_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO accounts (
                    user_id,
                    account_holder,
                    account_number,
                    account_type,
                    bank_name,
                    ifsc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, *values),
            )
            account_id = cursor.lastrowid

        connection.commit()
        return account_id
    finally:
        connection.close()


def _account_row_to_dict(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in row.keys() else None,
        "account_holder": row["account_holder"],
        "account_number": row["account_number"],
        "account_type": row["account_type"],
        "bank_name": row["bank_name"],
        "ifsc": row["ifsc"],
    }


def get_account(account_id, user_id=None):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, user_id, account_holder, account_number, account_type, bank_name, ifsc FROM accounts WHERE id = ? AND (? IS NULL OR user_id = ?)",
            (account_id, user_id, user_id),
        ).fetchone()
        return _account_row_to_dict(row)
    finally:
        connection.close()


def get_accounts(user_id=None):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, user_id, account_holder, account_number, account_type, bank_name, ifsc
            FROM accounts
            WHERE (? IS NULL OR user_id = ?)
            ORDER BY id
            """,
            (user_id, user_id),
        ).fetchall()
        return [_account_row_to_dict(row) for row in rows]
    finally:
        connection.close()


def get_statement_by_hash(account_id, hash_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT id, filename, created_at, account_id, hash_id,
                   statement_fingerprint, period_start, period_end,
                   transaction_count, total_debit, total_credit
            FROM statements
            WHERE account_id = ? AND hash_id = ?
            LIMIT 1
            """,
            (account_id, hash_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_statement_by_fingerprint(account_id, statement_fingerprint):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT id, filename, created_at, account_id, hash_id,
                   statement_fingerprint, period_start, period_end,
                   transaction_count, total_debit, total_credit
            FROM statements
            WHERE account_id = ? AND statement_fingerprint = ?
            LIMIT 1
            """,
            (account_id, statement_fingerprint),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_import_by_fingerprint(account_id, statement_fingerprint):
    """Find a previously completed statement import with the same financial identity."""
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT id, filename, created_at, account_id, file_hash,
                   statement_fingerprint, format, transaction_count,
                   new_transaction_count, duplicate_transaction_count,
                   total_debit, total_credit, status, statement_id
            FROM import_logs
            WHERE account_id = ?
              AND statement_fingerprint = ?
              AND status = 'COMPLETED'
            ORDER BY id ASC
            LIMIT 1
            """,
            (account_id, statement_fingerprint),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def save_import_log(
    user_id,
    account_id,
    filename,
    file_hash,
    statement_fingerprint,
    file_format,
    transaction_count,
    total_debit,
    total_credit,
    status,
    statement_id=None,
    new_transaction_count=None,
    duplicate_transaction_count=None,
):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO import_logs (
                user_id, account_id, filename, file_hash,
                statement_fingerprint, format, transaction_count,
                new_transaction_count, duplicate_transaction_count,
                total_debit, total_credit, status, statement_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, account_id, filename, file_hash,
                statement_fingerprint, file_format, transaction_count,
                new_transaction_count, duplicate_transaction_count,
                total_debit, total_credit, status, statement_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def save_statement(
    filename,
    account_id,
    hash_id,
    statement_fingerprint=None,
    period_start=None,
    period_end=None,
    transaction_count=None,
    total_debit=None,
    total_credit=None,
):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO statements (
                filename, created_at, account_id, hash_id,
                statement_fingerprint, period_start, period_end,
                transaction_count, total_debit, total_credit
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                datetime.now(timezone.utc).isoformat(),
                account_id,
                hash_id,
                statement_fingerprint,
                period_start,
                period_end,
                transaction_count,
                total_debit,
                total_credit,
            ),
        )
        statement_id = cursor.lastrowid
        connection.commit()
        return statement_id
    finally:
        connection.close()


def get_statement(statement_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT s.id, s.filename, s.created_at, s.account_id, s.hash_id,
                   s.statement_fingerprint, s.period_start, s.period_end,
                   s.transaction_count, s.total_debit, s.total_credit,
                   a.account_holder, a.account_number, a.account_type,
                   a.bank_name, a.ifsc
            FROM statements s
            LEFT JOIN accounts a ON a.id = s.account_id
            WHERE s.id = ?
            """,
            (statement_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "filename": row["filename"],
            "created_at": row["created_at"],
            "account_id": row["account_id"],
            "hash_id": row["hash_id"],
            "statement_fingerprint": row["statement_fingerprint"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "transaction_count": row["transaction_count"],
            "total_debit": row["total_debit"],
            "total_credit": row["total_credit"],
            "account": {
                "id": row["account_id"],
                "account_holder": row["account_holder"],
                "account_number": row["account_number"],
                "account_type": row["account_type"],
                "bank_name": row["bank_name"],
                "ifsc": row["ifsc"],
            } if row["account_id"] else None,
        }
    finally:
        connection.close()


def get_transactions(statement_id):
    """Return canonical transactions that appeared in a statement."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT t.id, t.statement_id, t.account_id, t.date, t.description,
                   t.debit, t.credit, t.balance, t.external_transaction_id,
                   t.canonical_fingerprint, t.merchant, t.category, t.confidence,
                   t.summary, t.is_subscription
            FROM transactions t
            JOIN transaction_sources ts ON ts.transaction_id = t.id
            WHERE ts.statement_id = ?
            ORDER BY ts.id
            """,
            (statement_id,),
        ).fetchall()
        return [_transaction_from_row(row) for row in rows]
    finally:
        connection.close()


def get_account_transactions(account_id):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT t.id, t.statement_id, t.account_id, t.date, t.description,
                   t.debit, t.credit, t.balance, t.external_transaction_id,
                   t.canonical_fingerprint, t.merchant, t.category, t.confidence,
                   t.summary, t.is_subscription
            FROM transactions t
            WHERE t.account_id = ?
            ORDER BY t.id
            """,
            (account_id,),
        ).fetchall()
        return [_transaction_from_row(row) for row in rows]
    finally:
        connection.close()


def get_account_statements(account_id):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, filename, created_at, account_id, hash_id,
                   statement_fingerprint, period_start, period_end,
                   transaction_count, total_debit, total_credit
            FROM statements
            WHERE account_id = ?
            ORDER BY id DESC
            """,
            (account_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _transaction_from_row(row):
    return Transaction(
        date=row["date"],
        description=row["description"],
        debit=row["debit"],
        credit=row["credit"],
        balance=row["balance"],
        external_transaction_id=row["external_transaction_id"],
        category=row["category"],
        merchant=row["merchant"],
        confidence=row["confidence"],
        summary=row["summary"],
        is_subscription=bool(row["is_subscription"]),
    )


def _candidate_transactions(cursor, account_id):
    rows = cursor.execute(
        """
        SELECT id, statement_id, account_id, date, description, debit, credit,
               balance, external_transaction_id, canonical_fingerprint,
               merchant, category, confidence, summary, is_subscription
        FROM transactions
        WHERE account_id = ?
        ORDER BY id
        """,
        (account_id,),
    ).fetchall()
    return [(row["id"], _transaction_from_row(row)) for row in rows]


def save_transactions(statement_id, transactions):
    """Persist statement rows while reusing existing canonical transactions.

    Returns counts describing what happened during the import. The existing
    transaction is never duplicated; the new statement is recorded as another
    source appearance through transaction_sources.
    """
    from .services.transaction_dedup import (
        build_candidate_indexes,
        build_transaction_fingerprint,
        find_best_transaction_match,
    )

    connection = get_connection()
    try:
        cursor = connection.cursor()
        statement = cursor.execute(
            "SELECT account_id FROM statements WHERE id = ?",
            (statement_id,),
        ).fetchone()
        if not statement or statement["account_id"] is None:
            raise ValueError("Statement account could not be determined.")

        account_id = statement["account_id"]
        candidates = _candidate_transactions(cursor, account_id)
        candidate_indexes = build_candidate_indexes(candidates)
        used_existing_ids = set()
        new_count = 0
        duplicate_count = 0

        for transaction in transactions:
            fingerprint = build_transaction_fingerprint(transaction)
            match = find_best_transaction_match(
                transaction,
                candidates,
                used_existing_ids,
                candidate_indexes,
            )

            if match:
                _, _, existing_id = match
                used_existing_ids.add(existing_id)
                duplicate_count += 1
                transaction_id = existing_id
            else:
                cursor.execute(
                    """
                    INSERT INTO transactions (
                        statement_id, account_id, date, description, debit, credit,
                        balance, external_transaction_id, canonical_fingerprint,
                        merchant, category, confidence, summary, is_subscription
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        statement_id,
                        account_id,
                        transaction.date,
                        transaction.description,
                        transaction.debit,
                        transaction.credit,
                        transaction.balance,
                        transaction.external_transaction_id,
                        fingerprint,
                        transaction.merchant,
                        transaction.category,
                        transaction.confidence,
                        transaction.summary,
                        int(transaction.is_subscription),
                    ),
                )
                transaction_id = cursor.lastrowid
                new_count += 1
                candidates.append((transaction_id, transaction))
                used_existing_ids.add(transaction_id)

            cursor.execute(
                """
                INSERT OR IGNORE INTO transaction_sources (
                    transaction_id, statement_id, statement_row_number, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    statement_id,
                    transaction.source_row_number,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        connection.commit()
        return {
            "new_transactions": new_count,
            "duplicate_transactions": duplicate_count,
            "total_rows": len(transactions),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
