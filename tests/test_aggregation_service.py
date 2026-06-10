from unittest.mock import MagicMock

import pytest

from RJK.services.aggregation_service import AggregationService

SAMPLE_ROWS = [
    {"FLAVOUR": "Vanilla", "REGION": "North", "SCORE": 0.85, "UNITS_SOLD": 1000},
    {"FLAVOUR": "Vanilla", "REGION": "South", "SCORE": 0.72, "UNITS_SOLD": 800},
    {"FLAVOUR": "Chocolate", "REGION": "North", "SCORE": 0.60, "UNITS_SOLD": 500},
    {"FLAVOUR": "Chocolate", "REGION": "South", "SCORE": 0.45, "UNITS_SOLD": 300},
]


def _make_svc(rows=None):
    rs = MagicMock()
    data = rows if rows is not None else SAMPLE_ROWS
    rs.run_report.return_value = {"rows": data, "row_count": len(data)}
    return AggregationService(rs)


class TestAggregationServicePreview:
    def test_sum_single_group(self):
        result = _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"UNITS_SOLD": "sum"})
        assert result["row_count"] == 2
        by_flavour = {r["flavour"]: r["units_sold_sum"] for r in result["rows"]}
        assert by_flavour["Vanilla"] == 1800
        assert by_flavour["Chocolate"] == 800

    def test_mean_single_group(self):
        result = _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"SCORE": "mean"})
        by_flavour = {r["flavour"]: r["score_mean"] for r in result["rows"]}
        assert abs(by_flavour["Vanilla"] - 0.785) < 1e-4

    def test_max_single_group(self):
        result = _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"SCORE": "max"})
        by_flavour = {r["flavour"]: r["score_max"] for r in result["rows"]}
        assert by_flavour["Vanilla"] == 0.85

    def test_min_single_group(self):
        result = _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"UNITS_SOLD": "min"})
        by_flavour = {r["flavour"]: r["units_sold_min"] for r in result["rows"]}
        assert by_flavour["Chocolate"] == 300

    def test_multi_col_different_funcs(self):
        result = _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"UNITS_SOLD": "sum", "SCORE": "mean"})
        assert result["row_count"] == 2
        row = next(r for r in result["rows"] if r["flavour"] == "Vanilla")
        assert row["units_sold_sum"] == 1800
        assert abs(row["score_mean"] - 0.785) < 1e-4

    def test_multi_group_by(self):
        result = _make_svc().preview("r.sql", {}, ["FLAVOUR", "REGION"], {"UNITS_SOLD": "sum"})
        assert result["row_count"] == 4

    def test_output_columns_lowercase(self):
        result = _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"UNITS_SOLD": "sum"})
        keys = set(result["rows"][0].keys())
        assert "flavour" in keys
        assert "units_sold_sum" in keys
        assert "FLAVOUR" not in keys

    def test_row_count_matches_rows(self):
        result = _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"UNITS_SOLD": "sum"})
        assert result["row_count"] == len(result["rows"])

    def test_unsupported_func_raises(self):
        with pytest.raises(ValueError, match="Unsupported function"):
            _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"UNITS_SOLD": "count"})

    def test_empty_group_by_raises(self):
        with pytest.raises(ValueError, match="group_by"):
            _make_svc().preview("r.sql", {}, [], {"UNITS_SOLD": "sum"})

    def test_unknown_value_col_raises(self):
        with pytest.raises(ValueError, match="Unknown value column"):
            _make_svc().preview("r.sql", {}, ["FLAVOUR"], {"NONEXISTENT": "sum"})

    def test_unknown_group_by_col_raises(self):
        with pytest.raises(ValueError, match="Unknown group-by"):
            _make_svc().preview("r.sql", {}, ["NOPE"], {"UNITS_SOLD": "sum"})

    def test_empty_rows_returns_empty(self):
        result = _make_svc(rows=[]).preview("r.sql", {}, ["FLAVOUR"], {"UNITS_SOLD": "sum"})
        assert result["rows"] == []
        assert result["row_count"] == 0

    def test_delegates_params_to_report_service(self):
        svc = _make_svc()
        svc.preview("r.sql", {"sales_date": "10-Jun-2026"}, ["FLAVOUR"], {"UNITS_SOLD": "sum"})
        svc.report_service.run_report.assert_called_once_with(
            "r.sql", {"sales_date": "10-Jun-2026"}, run_by="aggs-preview", limit=None
        )
