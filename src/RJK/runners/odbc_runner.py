import re
from pathlib import Path

from RJK.parser.sql_metadata_parser import extract_sql
from RJK.runners.base import BaseRunner

# ── Dialect detection ────────────────────────────────────────────────────────
# Keyed on substrings that appear in the ODBC Driver={...} value or DSN name.
# Order matters: more-specific patterns first.
_DIALECT_PATTERNS = [
    # SQL Server (Microsoft & FreeTDS)
    ("sqlserver",   ("sql server", "sqlserver", "sql native client", "freetds", "tds")),
    # Sybase / SAP ASE — same TOP N syntax as SQL Server
    ("sqlserver",   ("sybase", "adaptive server", "sap ase")),
    # Teradata — TOP N syntax (inject after SELECT)
    ("top_n",       ("teradata",)),
    # Oracle
    ("oracle",      ("oracle",)),
    # IBM DB2 / IBM i
    ("fetch_first", ("db2", "ibm i", "iseries", "ibm data server", "as400")),
    # Everything else: MySQL, PostgreSQL, SQLite, MariaDB, Snowflake, etc.
]


def _detect_dialect(conn_string: str) -> str:
    """
    Return a dialect key based on the ODBC Driver value or DSN in *conn_string*.
    Falls back to 'limit' (ANSI SQL / MySQL / PostgreSQL style).
    """
    cs = conn_string.lower()

    # Extract Driver={...} value if present
    m = re.search(r"driver\s*=\s*\{([^}]*)\}", cs)
    driver_val = m.group(1) if m else cs  # fall back to full string

    for dialect, keywords in _DIALECT_PATTERNS:
        if any(k in driver_val for k in keywords):
            return dialect

    return "limit"


def _apply_limit(sql: str, limit: int, dialect: str) -> str:
    """
    Append or inject a row-limit clause using syntax appropriate for *dialect*.
    Skips silently if the SQL already contains a limit construct.
    """
    sql_upper = sql.upper()

    if dialect in ("sqlserver", "top_n"):
        # SQL Server / Sybase / Teradata: SELECT [DISTINCT|ALL] TOP N ...
        # Skip if TOP already present (user wrote it explicitly)
        if re.search(r"\bTOP\s+\d+", sql, re.IGNORECASE):
            return sql
        # Inject TOP N immediately after SELECT (and optional DISTINCT/ALL)
        return re.sub(
            r"(?i)\b(SELECT\s+)(DISTINCT\s+|ALL\s+)?",
            rf"\1\2TOP {limit} ",
            sql,
            count=1,
        )

    if dialect == "oracle":
        # Oracle 12c+: FETCH FIRST N ROWS ONLY
        if "FETCH FIRST" in sql_upper:
            return sql
        return sql + f"\nFETCH FIRST {limit} ROWS ONLY"

    if dialect == "fetch_first":
        # DB2 / IBM i
        if "FETCH FIRST" in sql_upper:
            return sql
        return sql + f"\nFETCH FIRST {limit} ROWS ONLY"

    # Default: MySQL, PostgreSQL, SQLite, MariaDB, Snowflake
    if "LIMIT" in sql_upper:
        return sql
    return sql + f"\nLIMIT {limit}"


class OdbcRunner(BaseRunner):
    """Runs SQL against a real database via pyodbc."""

    def __init__(self, conn_string: str) -> None:
        self.conn_string = conn_string

    def run(
        self,
        sql_path: Path,
        params: dict,
        limit: int | None = 2000,
        conn_string: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> list[dict]:
        try:
            import pyodbc
        except ImportError as exc:
            raise RuntimeError(
                "pyodbc is not installed; install it or set MOCK_MODE=true"
            ) from exc

        content = sql_path.read_text(encoding="utf-8")
        sql = extract_sql(content).rstrip().rstrip(";")

        # Replace named :param placeholders with positional ? markers and
        # collect values in the same order.  Values are never interpolated into
        # the SQL string — the driver binds them at the protocol level.
        param_order: list = []

        def _replace(m: re.Match) -> str:
            key = m.group(1)
            if key in params:
                param_order.append(params[key])
                return "?"
            return m.group(0)  # leave unknown placeholders untouched

        sql = re.sub(r":([A-Za-z_]\w*)", _replace, sql)

        cs = conn_string or self.conn_string
        if limit is not None:
            dialect = _detect_dialect(cs)
            sql = _apply_limit(sql, int(limit), dialect)

        kwargs: dict = {}
        if username:
            kwargs["uid"] = username
        if password:
            kwargs["pwd"] = password

        conn = pyodbc.connect(cs, **kwargs)
        try:
            cursor = conn.cursor()
            cursor.execute(sql, param_order)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()
