from pathlib import Path

from RJK.parser.sql_metadata_parser import extract_sql
from RJK.runners.base import BaseRunner


class OdbcRunner(BaseRunner):
    """Runs SQL against a real database via pyodbc."""

    def __init__(self, conn_string: str) -> None:
        self.conn_string = conn_string

    def run(self, sql_path: Path, params: dict, limit: int | None = 2000) -> list[dict]:
        try:
            import pyodbc  # optional dependency
        except ImportError as exc:
            raise RuntimeError("pyodbc is not installed; install it or set MOCK_MODE=true") from exc

        content = sql_path.read_text(encoding="utf-8")
        sql = extract_sql(content).rstrip().rstrip(";")

        for key, val in params.items():
            sql = sql.replace(f":{key}", f"'{val}'")

        if limit is not None:
            sql += f"\nLIMIT {int(limit)}"

        conn = pyodbc.connect(self.conn_string)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()
