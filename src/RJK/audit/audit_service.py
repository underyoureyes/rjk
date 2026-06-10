import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_FILE = Path("data/audit.db")

_DDL = """
CREATE TABLE IF NOT EXISTS audit_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    report_path   TEXT    NOT NULL,
    params        TEXT,
    run_by        TEXT,
    ran_at        TEXT    NOT NULL,
    row_count     INTEGER,
    status        TEXT,
    error         TEXT
);
CREATE TABLE IF NOT EXISTS audit_signoffs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         INTEGER,
    report_path    TEXT    NOT NULL,
    signed_off_by  TEXT,
    signed_off_at  TEXT    NOT NULL,
    notes          TEXT,
    params         TEXT
);
CREATE TABLE IF NOT EXISTS agg_store (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    UNIQUE NOT NULL,
    report_path      TEXT    NOT NULL,
    run_id           INTEGER,
    group_by         TEXT,
    value_cols       TEXT,
    row_count        INTEGER,
    source_row_count INTEGER,
    size_bytes       INTEGER,
    format           TEXT    DEFAULT 'json',
    storage_path     TEXT,
    created_at       TEXT    DEFAULT (datetime('now'))
);
"""

# Safe migrations — each is a no-op if the column already exists
_MIGRATIONS = [
    "ALTER TABLE audit_signoffs ADD COLUMN params TEXT",
]


class AuditService:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_DDL)
        for sql in _MIGRATIONS:
            try:
                with self._connect() as conn:
                    conn.execute(sql)
            except Exception:
                pass  # column already exists

    def log_run(
        self,
        report_path: str,
        params: dict,
        run_by: str,
        row_count: int,
        status: str,
        error: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO audit_runs
                   (report_path, params, run_by, ran_at, row_count, status, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    report_path,
                    json.dumps(params),
                    run_by,
                    datetime.now(timezone.utc).isoformat(),
                    row_count,
                    status,
                    error,
                ),
            )
            return cur.lastrowid

    def log_signoff(
        self,
        run_id: int,
        report_path: str,
        signed_off_by: str,
        notes: str | None = None,
        params: dict | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO audit_signoffs
                   (run_id, report_path, signed_off_by, signed_off_at, notes, params)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    report_path,
                    signed_off_by,
                    datetime.now(timezone.utc).isoformat(),
                    notes,
                    json.dumps(params) if params is not None else None,
                ),
            )
            return cur.lastrowid

    def get_runs(self, limit: int = 200) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_runs ORDER BY ran_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_signoffs(self, limit: int = 200) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_signoffs ORDER BY signed_off_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def log_agg_persist(
        self,
        name: str,
        report_path: str,
        run_id: int | None,
        group_by: list,
        value_cols: dict,
        row_count: int,
        source_row_count: int,
        size_bytes: int,
        storage_path: str,
        fmt: str = "json",
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO agg_store
                   (name, report_path, run_id, group_by, value_cols,
                    row_count, source_row_count, size_bytes, format, storage_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    report_path,
                    run_id,
                    json.dumps(group_by),
                    json.dumps(value_cols),
                    row_count,
                    source_row_count,
                    size_bytes,
                    fmt,
                    storage_path,
                ),
            )
            return cur.lastrowid

    def get_agg_persists(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agg_store ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
