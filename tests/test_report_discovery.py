from pathlib import Path

import pytest

from RJK.discovery.report_discovery import build_report_tree, discover_reports


@pytest.fixture
def reports_dir(tmp_path):
    # Create a small fake reports tree
    r1 = tmp_path / "consumer" / "cards" / "report_a.sql"
    r1.parent.mkdir(parents=True)
    r1.write_text('/*\ntitle: "Report A"\ndescription: ""\nparams: {}\n*/\nSELECT 1')

    r2 = tmp_path / "consumer" / "loans" / "report_b.sql"
    r2.parent.mkdir(parents=True)
    r2.write_text('/*\ntitle: "Report B"\ndescription: ""\nparams: {}\n*/\nSELECT 2')

    return tmp_path


class TestDiscoverReports:
    def test_finds_all_sql(self, reports_dir):
        reports = discover_reports(reports_dir)
        assert len(reports) == 2

    def test_relative_paths(self, reports_dir):
        reports = discover_reports(reports_dir)
        paths = {r["path"] for r in reports}
        assert "consumer/cards/report_a.sql" in paths
        assert "consumer/loans/report_b.sql" in paths

    def test_titles_extracted(self, reports_dir):
        reports = discover_reports(reports_dir)
        titles = {r["title"] for r in reports}
        assert "Report A" in titles
        assert "Report B" in titles

    def test_empty_dir(self, tmp_path):
        assert discover_reports(tmp_path) == []

    def test_seed_reports(self):
        root = Path("reports")
        if not root.exists():
            pytest.skip("reports dir not found (run from project root)")
        reports = discover_reports(root)
        assert len(reports) == 3
        paths = {r["path"] for r in reports}
        assert "consumer/cards/cabm/model_results/agg_gcl_factors.sql" in paths
        assert "consumer/cards/cabm/model_results/vmx_gcl_rates_model.sql" in paths
        assert "consumer/cards/cabm/model_results/vmx_gcl_rates_ratio.sql" in paths


class TestBuildReportTree:
    def test_tree_structure(self, reports_dir):
        reports = discover_reports(reports_dir)
        tree = build_report_tree(reports)
        assert "consumer" in tree
        assert "_children" in tree["consumer"]

    def test_leaf_is_report(self, reports_dir):
        reports = discover_reports(reports_dir)
        tree = build_report_tree(reports)
        cards = tree["consumer"]["_children"]["cards"]["_children"]
        assert cards["report_a.sql"]["_type"] == "report"

    def test_empty_list_gives_empty_tree(self):
        assert build_report_tree([]) == {}
