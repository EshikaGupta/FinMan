import sqlite3
from datetime import datetime
from pathlib import Path

from .schemas import Transaction


DATABASE_PATH = Path("data/finance.db")


def get_connection():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )
    connection.row_factory = sqlite3.Row
    return connection


def _add_column_if_missing(
    cursor,
    table,
    column,
    definition,
):
    columns = {
        row["name"]
        for row in cursor.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
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
            CREATE TABLE IF NOT EXISTS statements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                statement_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                debit REAL,
                credit REAL,
                balance REAL,
                category TEXT,
                merchant TEXT,
                confidence REAL,
                summary TEXT,
                is_subscription INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (statement_id)
                    REFERENCES statements(id)
            )
            """
        )

        # Additive migration for databases created by older
        # versions of FinMan.
        _add_column_if_missing(
            cursor,
            "transactions",
            "category",
            "TEXT",
        )
        _add_column_if_missing(
            cursor,
            "transactions",
            "merchant",
            "TEXT",
        )
        _add_column_if_missing(
            cursor,
            "transactions",
            "confidence",
            "REAL",
        )
        _add_column_if_missing(
            cursor,
            "transactions",
            "summary",
            "TEXT",
        )
        _add_column_if_missing(
            cursor,
            "transactions",
            "is_subscription",
            "INTEGER NOT NULL DEFAULT 0",
        )

        connection.commit()

    finally:
        connection.close()


def get_transactions(statement_id):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                statement_id,
                date,
                description,
                debit,
                credit,
                balance,
                merchant,
                category,
                confidence,
                summary,
                is_subscription
            FROM transactions
            WHERE statement_id = ?
            ORDER BY id
            """,
            (statement_id,),
        )

        rows = cursor.fetchall()

        return [
            Transaction(
                date=row["date"],
                description=row["description"],
                debit=row["debit"],
                credit=row["credit"],
                balance=row["balance"],
                category=row["category"],
                merchant=row["merchant"],
                confidence=row["confidence"],
                summary=row["summary"],
                is_subscription=bool(
                    row["is_subscription"]
                ),
            )
            for row in rows
        ]

    finally:
        connection.close()


def save_statement(filename):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO statements (
                filename,
                created_at
            )
            VALUES (?, ?)
            """,
            (
                filename,
                datetime.utcnow().isoformat(),
            ),
        )

        statement_id = cursor.lastrowid
        connection.commit()

        return statement_id

    finally:
        connection.close()


def save_transactions(
    statement_id,
    transactions,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        for transaction in transactions:
            cursor.execute(
            """
            INSERT INTO transactions (
                statement_id,
                date,
                description,
                debit,
                credit,
                balance,
                merchant,
                category,
                confidence,
                summary,
                is_subscription
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                statement_id,
                transaction.date,
                transaction.description,
                transaction.debit,
                transaction.credit,
                transaction.balance,
                transaction.merchant,
                transaction.category,
                transaction.confidence,
                transaction.summary,
                int(transaction.is_subscription),
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
