"""Tests for sign-off API and user detection via HTTP."""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
from app import app

_REPORT = "demo/frosty_treats/sales/daily_product_sales.sql"


@pytest.fixture(autouse=True)
def use_tmp_audit(tmp_path, monkeypatch):
    from RJK.audit.audit_service import AuditService
    new_audit = AuditService(tmp_path / "test_audit.db")
    monkeypatch.setattr(app_module, "audit", new_audit)
    monkeypatch.setattr(app_module.report_service, "audit", new_audit)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def run_id(client):
    """Run a report and return the resulting run_id."""
    res = client.post("/api/reports/run", json={"path": _REPORT, "params": {}})
    assert res.status_code == 200
    return res.json()["run_id"]


# ---------------------------------------------------------------------------
# POST /api/signoff
# ---------------------------------------------------------------------------

class TestSignoffEndpoint:

    def test_valid_signoff_returns_200(self, client, run_id):
        res = client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
        })
        assert res.status_code == 200

    def test_returns_signoff_id(self, client, run_id):
        res = client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
        })
        data = res.json()
        assert "signoff_id" in data
        assert isinstance(data["signoff_id"], int)
        assert data["signoff_id"] >= 1

    def test_missing_run_id_returns_400(self, client):
        res = client.post("/api/signoff", json={
            "report_path": _REPORT,
            "signed_off_by": "alice",
        })
        assert res.status_code == 400

    def test_missing_report_path_returns_400(self, client, run_id):
        res = client.post("/api/signoff", json={
            "run_id": run_id,
            "signed_off_by": "alice",
        })
        assert res.status_code == 400

    def test_notes_stored(self, client, run_id):
        client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
            "notes": "Reviewed and approved",
        })
        signoffs = client.get("/api/audit").json()["signoffs"]
        assert signoffs[0]["notes"] == "Reviewed and approved"

    def test_notes_optional(self, client, run_id):
        res = client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
        })
        assert res.status_code == 200

    def test_signed_off_by_stored(self, client, run_id):
        client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
        })
        signoffs = client.get("/api/audit").json()["signoffs"]
        assert signoffs[0]["signed_off_by"] == "alice"

    def test_params_stored(self, client, run_id):
        client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
            "params": {"sales_date": "2024-01-01"},
        })
        signoffs = client.get("/api/audit").json()["signoffs"]
        assert "2024-01-01" in signoffs[0]["params"]

    def test_multiple_signoffs_all_recorded(self, client, run_id):
        for name in ("alice", "bob", "carol"):
            client.post("/api/signoff", json={
                "run_id": run_id,
                "report_path": _REPORT,
                "signed_off_by": name,
            })
        signoffs = client.get("/api/audit").json()["signoffs"]
        assert len(signoffs) == 3

    def test_signoff_appears_in_audit(self, client, run_id):
        client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
        })
        audit = client.get("/api/audit").json()
        assert len(audit["signoffs"]) == 1
        assert audit["signoffs"][0]["run_id"] == run_id

    def test_signoff_ids_increment(self, client, run_id):
        id1 = client.post("/api/signoff", json={
            "run_id": run_id, "report_path": _REPORT, "signed_off_by": "alice",
        }).json()["signoff_id"]
        id2 = client.post("/api/signoff", json={
            "run_id": run_id, "report_path": _REPORT, "signed_off_by": "bob",
        }).json()["signoff_id"]
        assert id2 > id1

    def test_anonymous_fallback_when_no_by_field(self, client, run_id):
        # signed_off_by defaults to "anonymous" when omitted
        res = client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
        })
        assert res.status_code == 200
        signoffs = client.get("/api/audit").json()["signoffs"]
        assert signoffs[0]["signed_off_by"] == "anonymous"


# ---------------------------------------------------------------------------
# GET /api/admin/status — user detection
# ---------------------------------------------------------------------------

class TestAdminStatusUserDetection:

    def test_returns_current_user(self, client, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "david")
        res = client.get("/api/admin/status")
        assert res.status_code == 200
        data = res.json()
        assert "current_user" in data
        assert "user_source" in data

    def test_os_user_detected_without_headers(self, client, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "testuser")
        res = client.get("/api/admin/status")
        data = res.json()
        assert data["current_user"] == "testuser"
        assert data["user_source"] == "os"

    def test_x_remote_user_header_used(self, client, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "os_user")
        res = client.get("/api/admin/status", headers={"X-Remote-User": "sso_alice"})
        data = res.json()
        assert data["current_user"] == "sso_alice"
        assert data["user_source"] == "header"

    def test_remote_user_header_used(self, client, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "os_user")
        res = client.get("/api/admin/status", headers={"Remote-User": "sso_bob"})
        data = res.json()
        assert data["current_user"] == "sso_bob"
        assert data["user_source"] == "header"

    def test_x_forwarded_user_header_used(self, client, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "os_user")
        res = client.get("/api/admin/status", headers={"X-Forwarded-User": "sso_carol"})
        data = res.json()
        assert data["current_user"] == "sso_carol"
        assert data["user_source"] == "header"

    def test_header_takes_precedence_over_os(self, client, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "local_user")
        res = client.get("/api/admin/status", headers={"X-Remote-User": "sso_user"})
        data = res.json()
        assert data["current_user"] == "sso_user"
        assert data["user_source"] == "header"

    def test_header_user_lowercased(self, client, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "os_user")
        res = client.get("/api/admin/status", headers={"X-Remote-User": "ALICE"})
        assert res.json()["current_user"] == "alice"

    def test_response_includes_required_fields(self, client):
        res = client.get("/api/admin/status")
        data = res.json()
        for field in ("current_user", "user_source", "auth_enabled",
                      "local_run", "is_admin", "unix_available"):
            assert field in data, f"missing field: {field}"

    def test_local_run_true_when_auth_disabled(self, client):
        # Default config has AUTH_ENABLED=false
        res = client.get("/api/admin/status")
        assert res.json()["local_run"] is True
        assert res.json()["auth_enabled"] is False


# ---------------------------------------------------------------------------
# Sign-off flow: run → sign off → verify audit chain
# ---------------------------------------------------------------------------

class TestSignoffAuditChain:

    def test_run_then_signoff_linked_by_run_id(self, client):
        run_res = client.post("/api/reports/run", json={"path": _REPORT, "params": {}})
        run_id = run_res.json()["run_id"]

        client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
            "notes": "End-to-end check",
        })

        audit = client.get("/api/audit").json()
        assert len(audit["runs"]) == 1
        assert len(audit["signoffs"]) == 1
        assert audit["runs"][0]["id"] == run_id
        assert audit["signoffs"][0]["run_id"] == run_id

    def test_signoff_timestamp_present(self, client, run_id):
        client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
        })
        signoffs = client.get("/api/audit").json()["signoffs"]
        assert signoffs[0].get("signed_off_at") not in (None, "")

    def test_signoff_report_path_stored(self, client, run_id):
        client.post("/api/signoff", json={
            "run_id": run_id,
            "report_path": _REPORT,
            "signed_off_by": "alice",
        })
        signoffs = client.get("/api/audit").json()["signoffs"]
        assert signoffs[0]["report_path"] == _REPORT
