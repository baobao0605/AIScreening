"""Repository for title-abstract project records."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3

from src.utils import utc_now


TA_NEW = "NEW"
TA_SCREENING = "SCREENING"
TA_DONE = "DONE"
TA_SCREEN_FAILED_RETRY = "SCREEN_FAILED_RETRY"
TA_SKIPPED = "SKIPPED"
TA_FAILED = "FAILED"


@dataclass(slots=True)
class TARecord:
    id: int
    source_excel_path: str
    sheet_name: str
    row_index: int
    title: str
    abstract: str
    record_hash: str
    status: str
    decision: str | None
    exclude_reason: str
    construct: str | None
    note: str | None
    screening_model: str | None
    error: str | None
    raw_response: str | None
    created_at: str
    updated_at: str


def _to_record(row: sqlite3.Row) -> TARecord:
    return TARecord(**dict(row))


def record_hash(title: str, abstract: str) -> str:
    key = f"{title.strip().casefold()}||{abstract.strip().casefold()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


class TARepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS title_abstract_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_excel_path TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                abstract TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                decision TEXT,
                exclude_reason TEXT NOT NULL DEFAULT '',
                construct TEXT,
                note TEXT,
                screening_model TEXT,
                error TEXT,
                raw_response TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_excel_path, record_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_ta_status ON title_abstract_records(status);
            """
        )
        self.connection.commit()

    def upsert_rows(self, source_excel_path: Path, sheet_name: str, rows: list[tuple[int, str, str]]) -> int:
        inserted = 0
        for row_index, title, abstract in rows:
            if not title and not abstract:
                continue
            hashed = record_hash(title, abstract)
            existing = self.connection.execute(
                "SELECT id FROM title_abstract_records WHERE source_excel_path = ? AND record_hash = ?",
                (str(source_excel_path), hashed),
            ).fetchone()
            if existing:
                continue
            now = utc_now()
            self.connection.execute(
                """
                INSERT INTO title_abstract_records (
                    source_excel_path, sheet_name, row_index, title, abstract, record_hash,
                    status, decision, exclude_reason, construct, note, screening_model, error, raw_response,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, '', NULL, NULL, NULL, NULL, NULL, ?, ?)
                """,
                (str(source_excel_path), sheet_name, row_index, title, abstract, hashed, TA_NEW, now, now),
            )
            inserted += 1
        self.connection.commit()
        return inserted

    def queue(self, statuses: tuple[str, ...]) -> list[TARecord]:
        placeholders = ", ".join("?" for _ in statuses)
        rows = self.connection.execute(
            f"SELECT * FROM title_abstract_records WHERE status IN ({placeholders}) ORDER BY id",
            list(statuses),
        ).fetchall()
        return [_to_record(row) for row in rows]

    def set_screening(self, record_id: int) -> None:
        self.connection.execute(
            "UPDATE title_abstract_records SET status = ?, updated_at = ? WHERE id = ?",
            (TA_SCREENING, utc_now(), record_id),
        )
        self.connection.commit()

    def mark_done(
        self,
        record_id: int,
        *,
        decision: str,
        exclude_reason: str,
        construct: str,
        note: str,
        screening_model: str,
        raw_response: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE title_abstract_records
            SET status = ?, decision = ?, exclude_reason = ?, construct = ?, note = ?,
                screening_model = ?, error = NULL, raw_response = ?, updated_at = ?
            WHERE id = ?
            """,
            (TA_DONE, decision, exclude_reason, construct, note, screening_model, raw_response, utc_now(), record_id),
        )
        self.connection.commit()

    def mark_failed(self, record_id: int, error_message: str, raw_response: str | None = None) -> None:
        self.connection.execute(
            """
            UPDATE title_abstract_records
            SET status = ?, error = ?, raw_response = ?, updated_at = ?
            WHERE id = ?
            """,
            (TA_SCREEN_FAILED_RETRY, error_message, raw_response, utc_now(), record_id),
        )
        self.connection.commit()

    def status_summary(self) -> dict[str, int]:
        total = self.connection.execute("SELECT COUNT(*) FROM title_abstract_records").fetchone()[0]
        done = self.connection.execute("SELECT COUNT(*) FROM title_abstract_records WHERE status = ?", (TA_DONE,)).fetchone()[0]
        new = self.connection.execute("SELECT COUNT(*) FROM title_abstract_records WHERE status = ?", (TA_NEW,)).fetchone()[0]
        failed = self.connection.execute(
            "SELECT COUNT(*) FROM title_abstract_records WHERE status IN (?, ?)",
            (TA_SCREEN_FAILED_RETRY, TA_FAILED),
        ).fetchone()[0]
        maybe = self.connection.execute("SELECT COUNT(*) FROM title_abstract_records WHERE decision = 'MAYBE'").fetchone()[0]
        include = self.connection.execute("SELECT COUNT(*) FROM title_abstract_records WHERE decision = 'INCLUDE'").fetchone()[0]
        exclude = self.connection.execute("SELECT COUNT(*) FROM title_abstract_records WHERE decision = 'EXCLUDE'").fetchone()[0]
        return {
            "total_discovered": total,
            "done": done,
            "new": new,
            "failed": failed,
            "maybe": maybe,
            "include": include,
            "exclude": exclude,
        }

    def export_rows(self) -> list[dict[str, str]]:
        rows = self.connection.execute(
            """
            SELECT
                title AS "Title",
                abstract AS "Abstract",
                COALESCE(decision, '') AS "Decision",
                COALESCE(exclude_reason, '') AS "Exclude reason",
                COALESCE(construct, '') AS "Construct",
                COALESCE(note, '') AS "Note",
                COALESCE(screening_model, '') AS "Model",
                status AS "Status",
                COALESCE(error, '') AS "Error"
            FROM title_abstract_records
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def table_rows(self, limit: int = 1000) -> list[dict[str, str]]:
        rows = self.connection.execute(
            """
            SELECT
                title AS "Title",
                abstract AS "Abstract",
                COALESCE(decision, '') AS "Decision",
                COALESCE(exclude_reason, '') AS "Exclude reason",
                COALESCE(construct, '') AS "Construct",
                COALESCE(note, '') AS "Note",
                COALESCE(screening_model, '') AS "Model",
                status AS "Status",
                COALESCE(error, '') AS "Error"
            FROM title_abstract_records
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

