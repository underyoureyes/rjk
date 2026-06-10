from pathlib import Path

import pytest

from RJK.parser.sql_metadata_parser import extract_sql, parse_sql_metadata

SQL_WITH_META = """\
/*
title: "Test Report"
description: "A test"
owner: "Analytics"
tags: [test, sales]
params:
  run_date:
    type: date
    label: "Run Date"
    default: "today"
  flavour:
    type: select
    label: "Flavour"
    options: [ALL, Vanilla, Chocolate]
    default: ALL
*/

SELECT 1 AS value FROM dual
"""

SQL_NO_META = "SELECT 1 AS value FROM dual"


@pytest.fixture
def sql_file(tmp_path):
    f = tmp_path / "report.sql"
    f.write_text(SQL_WITH_META)
    return f


@pytest.fixture
def sql_file_no_meta(tmp_path):
    f = tmp_path / "bare.sql"
    f.write_text(SQL_NO_META)
    return f


class TestParseMetadata:
    def test_title(self, sql_file):
        meta = parse_sql_metadata(sql_file)
        assert meta["title"] == "Test Report"

    def test_description(self, sql_file):
        meta = parse_sql_metadata(sql_file)
        assert meta["description"] == "A test"

    def test_owner(self, sql_file):
        meta = parse_sql_metadata(sql_file)
        assert meta["owner"] == "Analytics"

    def test_tags(self, sql_file):
        meta = parse_sql_metadata(sql_file)
        assert meta["tags"] == ["test", "sales"]

    def test_params_keys(self, sql_file):
        meta = parse_sql_metadata(sql_file)
        assert set(meta["params"].keys()) == {"run_date", "flavour"}

    def test_param_type(self, sql_file):
        meta = parse_sql_metadata(sql_file)
        assert meta["params"]["run_date"]["type"] == "date"

    def test_param_options(self, sql_file):
        meta = parse_sql_metadata(sql_file)
        assert meta["params"]["flavour"]["options"] == ["ALL", "Vanilla", "Chocolate"]

    def test_no_meta_returns_defaults(self, sql_file_no_meta):
        meta = parse_sql_metadata(sql_file_no_meta)
        assert meta["title"] == "bare"
        assert meta["params"] == {}

    def test_seed_file_daily_sales(self):
        sql_path = Path("reports/frosty_treats/sales/daily_product_sales.sql")
        if not sql_path.exists():
            pytest.skip("seed file not found (run from project root)")
        meta = parse_sql_metadata(sql_path)
        assert meta["title"] == "Ice Cream Daily Sales"
        assert "sales_date" in meta["params"]


class TestExtractSql:
    def test_strips_comment(self):
        sql = extract_sql(SQL_WITH_META)
        assert "/*" not in sql
        assert "SELECT 1" in sql

    def test_bare_sql_unchanged(self):
        sql = extract_sql(SQL_NO_META)
        assert sql == SQL_NO_META.strip()
