"""Integration tests for the FastAPI app — runs against a real (tmp) audit DB and real seed reports."""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the test is always run from the project root (pytest.ini sets rootdir)
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
from app import app


@pytest.fixture(autouse=True)
def use_tmp_audit(tmp_path, monkeypatch):
    """Redirect audit DB to a temporary file for each test."""
    from RJK.audit.audit_service import AuditService
    new_audit = AuditService(tmp_path / "test_audit.db")
    monkeypatch.setattr(app_module, "audit", new_audit)
    monkeypatch.setattr(app_module.report_service, "audit", new_audit)


@pytest.fixture
def client():
    return TestClient(app)


class TestRoot:
    def test_returns_html(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "RJK Report Framework" in res.text


class TestListReports:
    def test_returns_reports(self, client):
        res = client.get("/api/reports")
        assert res.status_code == 200
        data = res.json()
        assert "reports" in data
        assert len(data["reports"]) == 3

    def test_tree_present(self, client):
        res = client.get("/api/reports")
        assert "tree" in res.json()

    def test_report_paths(self, client):
        paths = {r["path"] for r in client.get("/api/reports").json()["reports"]}
        assert "consumer/cards/cabm/model_results/agg_gcl_factors.sql" in paths


class TestReportMeta:
    def test_known_report(self, client):
        res = client.get("/api/reports/meta?path=consumer/cards/cabm/model_results/agg_gcl_factors.sql")
        assert res.status_code == 200
        meta = res.json()
        assert meta["title"] == "Aggregate GCL Factors"
        assert "run_date" in meta["params"]

    def test_mock_block_not_exposed(self, client):
        res = client.get("/api/reports/meta?path=consumer/cards/cabm/model_results/agg_gcl_factors.sql")
        assert "mock" not in res.json()

    def test_unknown_report_404(self, client):
        res = client.get("/api/reports/meta?path=does/not/exist.sql")
        assert res.status_code == 404


class TestRunReport:
    def test_run_returns_rows(self, client):
        res = client.post("/api/reports/run", json={
            "path": "consumer/cards/cabm/model_results/agg_gcl_factors.sql",
            "params": {"run_date": "09-Jun-2026"}
        })
        assert res.status_code == 200
        data = res.json()
        assert data["row_count"] == 27_000
        assert len(data["rows"]) == 27_000
        assert "run_id" in data

    def test_run_unknown_404(self, client):
        res = client.post("/api/reports/run", json={"path": "no/such.sql", "params": {}})
        assert res.status_code == 404

    def test_run_missing_path_400(self, client):
        res = client.post("/api/reports/run", json={"params": {}})
        assert res.status_code == 400


class TestExportCsv:
    def test_returns_csv(self, client):
        res = client.post("/api/reports/export/csv", json={
            "path": "consumer/cards/cabm/model_results/vmx_gcl_rates_model.sql",
            "params": {}
        })
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        lines = res.text.splitlines()
        assert len(lines) == 13_501  # header + 13500 rows

    def test_csv_has_header(self, client):
        res = client.post("/api/reports/export/csv", json={
            "path": "consumer/cards/cabm/model_results/vmx_gcl_rates_model.sql",
            "params": {}
        })
        header = res.text.splitlines()[0]
        assert "MODEL_VERSION" in header


class TestExportExcel:
    def test_returns_xlsx(self, client):
        res = client.post("/api/reports/export/excel", json={
            "path": "consumer/cards/cabm/model_results/vmx_gcl_rates_ratio.sql",
            "params": {}
        })
        assert res.status_code == 200
        ct = res.headers["content-type"]
        assert "spreadsheetml" in ct or "excel" in ct or "octet-stream" in ct


class TestAudit:
    def test_empty_initially(self, client):
        data = client.get("/api/audit").json()
        assert data["runs"] == []
        assert data["signoffs"] == []

    def test_run_appears_in_audit(self, client):
        client.post("/api/reports/run", json={
            "path": "consumer/cards/cabm/model_results/agg_gcl_factors.sql",
            "params": {}
        })
        data = client.get("/api/audit").json()
        assert len(data["runs"]) == 1
        assert data["runs"][0]["status"] == "success"


class TestSignoff:
    def test_signoff_recorded(self, client):
        run_res = client.post("/api/reports/run", json={
            "path": "consumer/cards/cabm/model_results/agg_gcl_factors.sql",
            "params": {}
        })
        run_id = run_res.json()["run_id"]
        so_res = client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": "consumer/cards/cabm/model_results/agg_gcl_factors.sql",
            "signed_off_by": "alice",
            "notes": "Looks good"
        })
        assert so_res.status_code == 200
        assert "signoff_id" in so_res.json()

    def test_signoff_missing_fields_400(self, client):
        res = client.post("/api/signoff", json={"signed_off_by": "alice"})
        assert res.status_code == 400
