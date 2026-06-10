from pathlib import Path

import pytest

from RJK.runners.mock_runner import MockRunner

SQL_WITH_MOCK = """\
/*
title: "Mock Test"
description: ""
params: {}
mock:
  dimensions:
    FLAVOUR: [Vanilla, Chocolate, Strawberry]
    REGION: [North, South]
  numerics:
    SCORE:
      min: 0.0
      max: 1.0
      decimals: 4
    COUNT:
      min: 10
      max: 1000
      decimals: 0
*/
SELECT 1
"""

SQL_NO_MOCK = "/*\ntitle: 'x'\nparams: {}\n*/\nSELECT 1"


@pytest.fixture
def sql_file(tmp_path):
    f = tmp_path / "mock_report.sql"
    f.write_text(SQL_WITH_MOCK)
    return f


@pytest.fixture
def sql_no_mock(tmp_path):
    f = tmp_path / "no_mock.sql"
    f.write_text(SQL_NO_MOCK)
    return f


class TestMockRunner:
    def test_row_count(self, sql_file):
        rows = MockRunner().run(sql_file, {})
        assert len(rows) == 6  # 3 × 2

    def test_column_names(self, sql_file):
        rows = MockRunner().run(sql_file, {})
        assert set(rows[0].keys()) == {"FLAVOUR", "REGION", "SCORE", "COUNT"}

    def test_dimensions_are_strings(self, sql_file):
        rows = MockRunner().run(sql_file, {})
        assert all(isinstance(r["FLAVOUR"], str) for r in rows)

    def test_score_in_range(self, sql_file):
        rows = MockRunner().run(sql_file, {})
        assert all(0.0 <= r["SCORE"] <= 1.0 for r in rows)

    def test_count_is_integer(self, sql_file):
        rows = MockRunner().run(sql_file, {})
        assert all(isinstance(r["COUNT"], int) for r in rows)

    def test_count_in_range(self, sql_file):
        rows = MockRunner().run(sql_file, {})
        assert all(10 <= r["COUNT"] <= 1000 for r in rows)

    def test_no_mock_config_returns_message(self, sql_no_mock):
        rows = MockRunner().run(sql_no_mock, {})
        assert len(rows) == 1
        assert "message" in rows[0]

    def test_seed_daily_sales_row_count(self):
        sql_path = Path("reports/frosty_treats/sales/daily_product_sales.sql")
        if not sql_path.exists():
            pytest.skip("seed file not found")
        rows = MockRunner().run(sql_path, {}, limit=None)
        assert len(rows) == 672  # 8 FLAVOUR × 6 REGION × 14 SALES_DATE

    def test_seed_daily_sales_has_month_column(self):
        sql_path = Path("reports/frosty_treats/sales/daily_product_sales.sql")
        if not sql_path.exists():
            pytest.skip("seed file not found")
        rows = MockRunner().run(sql_path, {}, limit=None)
        assert "MONTH" in rows[0]

    def test_seed_daily_close_prices_row_count(self):
        sql_path = Path("reports/stock_market/prices/daily_close_prices.sql")
        if not sql_path.exists():
            pytest.skip("seed file not found")
        rows = MockRunner().run(sql_path, {}, limit=None)
        # 7 tickers × ~522 weekdays in last 730 days; exact count varies by run date
        assert 3000 < len(rows) < 4200
