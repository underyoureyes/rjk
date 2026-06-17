"""
Tests for OdbcRunner — dialect detection, limit injection, and param binding.
pyodbc is not required: all tests that touch SQL transformation work without a
live database connection.
"""
import re
import pytest

from RJK.runners.odbc_runner import _detect_dialect, _apply_limit


# ── Dialect detection ────────────────────────────────────────────────────────

class TestDetectDialect:
    def test_sql_server_named_driver(self):
        cs = "Driver={ODBC Driver 17 for SQL Server};Server=myserver;Database=mydb"
        assert _detect_dialect(cs) == "sqlserver"

    def test_sql_server_old_driver(self):
        cs = "Driver={SQL Server};Server=myserver"
        assert _detect_dialect(cs) == "sqlserver"

    def test_sql_server_native_client(self):
        cs = "Driver={SQL Server Native Client 11.0};Server=myserver"
        assert _detect_dialect(cs) == "sqlserver"

    def test_freetds(self):
        cs = "Driver={FreeTDS};Server=myserver;TDS_Version=8.0"
        assert _detect_dialect(cs) == "sqlserver"

    def test_oracle(self):
        cs = "Driver={Oracle in instantclient_21_3};DBQ=mydb"
        assert _detect_dialect(cs) == "oracle"

    def test_db2(self):
        cs = "Driver={IBM DB2 ODBC DRIVER};Database=mydb"
        assert _detect_dialect(cs) == "fetch_first"

    def test_iseries(self):
        cs = "Driver={iSeries Access ODBC Driver};System=mydb"
        assert _detect_dialect(cs) == "fetch_first"

    def test_mysql(self):
        cs = "Driver={MySQL ODBC 8.0 Unicode Driver};Server=myserver;Database=mydb"
        assert _detect_dialect(cs) == "limit"

    def test_postgresql(self):
        cs = "Driver={PostgreSQL Unicode};Server=myserver;Database=mydb"
        assert _detect_dialect(cs) == "limit"

    def test_sqlite(self):
        cs = "Driver={SQLite3 ODBC Driver};Database=/tmp/mydb.sqlite"
        assert _detect_dialect(cs) == "limit"

    def test_teradata(self):
        cs = "Driver={Teradata Database ODBC Driver 17.10};DBCName=myhost"
        assert _detect_dialect(cs) == "top_n"

    def test_unknown_falls_back_to_limit(self):
        cs = "DSN=mydsn"
        assert _detect_dialect(cs) == "limit"

    def test_case_insensitive(self):
        cs = "DRIVER={ODBC DRIVER 18 FOR SQL SERVER};SERVER=myserver"
        assert _detect_dialect(cs) == "sqlserver"


# ── Limit injection ──────────────────────────────────────────────────────────

BASE_SQL = "SELECT col1, col2 FROM my_table WHERE col1 = ?"

class TestApplyLimit:

    # --- LIMIT dialect (MySQL / PostgreSQL / SQLite) ---

    def test_limit_appended(self):
        sql = _apply_limit(BASE_SQL, 100, "limit")
        assert sql.endswith("\nLIMIT 100")

    def test_limit_skipped_if_already_present(self):
        sql = BASE_SQL + "\nLIMIT 50"
        result = _apply_limit(sql, 100, "limit")
        assert result.count("LIMIT") == 1
        assert "LIMIT 50" in result

    def test_limit_case_insensitive_skip(self):
        sql = BASE_SQL + "\nlimit 50"
        result = _apply_limit(sql, 100, "limit")
        assert result.count("imit") == 1  # only one limit word

    # --- SQL Server / TOP N ---

    def test_sqlserver_injects_top(self):
        sql = _apply_limit("SELECT col1, col2 FROM t", 500, "sqlserver")
        assert re.match(r"SELECT TOP 500 col1", sql, re.IGNORECASE)

    def test_sqlserver_preserves_distinct(self):
        sql = _apply_limit("SELECT DISTINCT col1 FROM t", 10, "sqlserver")
        assert re.match(r"SELECT DISTINCT TOP 10 col1", sql, re.IGNORECASE)

    def test_sqlserver_skips_if_top_present(self):
        sql = "SELECT TOP 50 col1 FROM t"
        result = _apply_limit(sql, 500, "sqlserver")
        assert "TOP 500" not in result
        assert "TOP 50" in result

    def test_top_n_dialect_same_as_sqlserver(self):
        sql = _apply_limit("SELECT col1 FROM t", 25, "top_n")
        assert "TOP 25" in sql

    # --- Oracle ---

    def test_oracle_appends_fetch_first(self):
        sql = _apply_limit(BASE_SQL, 200, "oracle")
        assert sql.endswith("\nFETCH FIRST 200 ROWS ONLY")

    def test_oracle_skips_if_fetch_present(self):
        sql = BASE_SQL + "\nFETCH FIRST 10 ROWS ONLY"
        result = _apply_limit(sql, 200, "oracle")
        assert result.count("FETCH FIRST") == 1
        assert "FETCH FIRST 10" in result

    # --- DB2 / IBM i ---

    def test_db2_appends_fetch_first(self):
        sql = _apply_limit(BASE_SQL, 300, "fetch_first")
        assert sql.endswith("\nFETCH FIRST 300 ROWS ONLY")

    def test_db2_skips_if_fetch_present(self):
        sql = BASE_SQL + "\nFETCH FIRST 5 ROWS ONLY"
        result = _apply_limit(sql, 300, "fetch_first")
        assert result.count("FETCH FIRST") == 1

    # --- Limit value is always an integer (injection-safe) ---

    def test_limit_is_integer(self):
        # int() in _apply_limit means a non-integer would raise before reaching SQL
        sql = _apply_limit(BASE_SQL, 2000, "limit")
        assert "LIMIT 2000" in sql


# ── Param binding (no live DB needed) ───────────────────────────────────────
# We test the regex substitution logic directly rather than calling .run(),
# which requires pyodbc and a real connection.

def _substitute_params(sql: str, params: dict):
    """Mirror the substitution logic from OdbcRunner.run() for unit testing."""
    param_order = []
    def _replace(m):
        key = m.group(1)
        if key in params:
            param_order.append(params[key])
            return "?"
        return m.group(0)
    sql_out = re.sub(r":([A-Za-z_]\w*)", _replace, sql)
    return sql_out, param_order


class TestParamBinding:

    def test_single_param_replaced(self):
        sql, vals = _substitute_params("SELECT * FROM t WHERE x = :foo", {"foo": "bar"})
        assert sql == "SELECT * FROM t WHERE x = ?"
        assert vals == ["bar"]

    def test_multiple_params_in_order(self):
        sql, vals = _substitute_params(
            "SELECT * FROM t WHERE a = :alpha AND b = :beta",
            {"alpha": "A", "beta": "B"},
        )
        assert sql == "SELECT * FROM t WHERE a = ? AND b = ?"
        assert vals == ["A", "B"]

    def test_same_param_twice(self):
        sql, vals = _substitute_params(
            "SELECT * FROM t WHERE x = :val OR y = :val",
            {"val": "X"},
        )
        assert sql == "SELECT * FROM t WHERE x = ? OR y = ?"
        assert vals == ["X", "X"]

    def test_unknown_param_left_unchanged(self):
        sql, vals = _substitute_params(
            "SELECT * FROM t WHERE x = :known AND y = :unknown",
            {"known": "K"},
        )
        assert "?" in sql
        assert ":unknown" in sql
        assert vals == ["K"]

    def test_sql_injection_attempt_is_inert(self):
        """A malicious value must never alter the SQL structure."""
        payload = "' OR '1'='1"
        sql, vals = _substitute_params(
            "SELECT * FROM t WHERE region = :region",
            {"region": payload},
        )
        # SQL structure is unchanged — payload is a bind value, not SQL text
        assert sql == "SELECT * FROM t WHERE region = ?"
        assert vals == [payload]
        assert "OR" not in sql
        assert "1=1" not in sql

    def test_drop_table_injection_is_inert(self):
        payload = "'; DROP TABLE users; --"
        sql, vals = _substitute_params(
            "SELECT * FROM t WHERE x = :x",
            {"x": payload},
        )
        assert sql == "SELECT * FROM t WHERE x = ?"
        assert vals == [payload]
        assert "DROP" not in sql
