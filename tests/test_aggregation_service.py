from unittest.mock import MagicMock

import pytest

from RJK.services.aggregation_service import AggregationService

SAMPLE_ROWS = [
    {"SEGMENT": "PRIME", "RISK_BAND": "BAND_1", "SCORE": 0.85, "N": 1000},
    {"SEGMENT": "PRIME", "RISK_BAND": "BAND_2", "SCORE": 0.72, "N": 800},
    {"SEGMENT": "NEAR_PRIME", "RISK_BAND": "BAND_1", "SCORE": 0.60, "N": 500},
    {"SEGMENT": "NEAR_PRIME", "RISK_BAND": "BAND_2", "SCORE": 0.45, "N": 300},
]


def _make_svc(rows=None):
    rs = MagicMock()
    data = rows if rows is not None else SAMPLE_ROWS
    rs.run_report.return_value = {"rows": data, "row_count": len(data)}
    return AggregationService(rs)


class TestAggregationServicePreview:
    def test_sum_single_group(self):
        result = _make_svc().preview("r.sql", {}, ["SEGMENT"], "N", "sum")
        assert result["row_count"] == 2
        by_seg = {r["SEGMENT"]: r["N"] for r in result["rows"]}
        assert by_seg["PRIME"] == 1800
        assert by_seg["NEAR_PRIME"] == 800

    def test_mean_single_group(self):
        result = _make_svc().preview("r.sql", {}, ["SEGMENT"], "SCORE", "mean")
        by_seg = {r["SEGMENT"]: r["SCORE"] for r in result["rows"]}
        assert abs(by_seg["PRIME"] - 0.785) < 1e-4

    def test_max_single_group(self):
        result = _make_svc().preview("r.sql", {}, ["SEGMENT"], "SCORE", "max")
        by_seg = {r["SEGMENT"]: r["SCORE"] for r in result["rows"]}
        assert by_seg["PRIME"] == 0.85

    def test_min_single_group(self):
        result = _make_svc().preview("r.sql", {}, ["SEGMENT"], "N", "min")
        by_seg = {r["SEGMENT"]: r["N"] for r in result["rows"]}
        assert by_seg["NEAR_PRIME"] == 300

    def test_multi_group_by(self):
        result = _make_svc().preview("r.sql", {}, ["SEGMENT", "RISK_BAND"], "N", "sum")
        assert result["row_count"] == 4

    def test_row_count_matches_rows(self):
        result = _make_svc().preview("r.sql", {}, ["SEGMENT"], "N", "sum")
        assert result["row_count"] == len(result["rows"])

    def test_unsupported_func_raises(self):
        with pytest.raises(ValueError, match="Unsupported function"):
            _make_svc().preview("r.sql", {}, ["SEGMENT"], "N", "count")

    def test_empty_group_by_raises(self):
        with pytest.raises(ValueError, match="group_by"):
            _make_svc().preview("r.sql", {}, [], "N", "sum")

    def test_unknown_value_col_raises(self):
        with pytest.raises(ValueError, match="not found"):
            _make_svc().preview("r.sql", {}, ["SEGMENT"], "NONEXISTENT", "sum")

    def test_unknown_group_by_col_raises(self):
        with pytest.raises(ValueError, match="Unknown group-by"):
            _make_svc().preview("r.sql", {}, ["NOPE"], "N", "sum")

    def test_empty_rows_returns_empty(self):
        result = _make_svc(rows=[]).preview("r.sql", {}, ["SEGMENT"], "N", "sum")
        assert result["rows"] == []
        assert result["row_count"] == 0

    def test_delegates_params_to_report_service(self):
        svc = _make_svc()
        svc.preview("r.sql", {"run_date": "2024-01-01"}, ["SEGMENT"], "N", "sum")
        svc.report_service.run_report.assert_called_once_with(
            "r.sql", {"run_date": "2024-01-01"}, run_by="aggs-preview"
        )
