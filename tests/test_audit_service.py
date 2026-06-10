import pytest

from RJK.audit.audit_service import AuditService


@pytest.fixture
def audit(tmp_path):
    return AuditService(db_path=tmp_path / "test_audit.db")


class TestLogRun:
    def test_returns_integer_id(self, audit):
        run_id = audit.log_run("some/report.sql", {}, "alice", 100, "success")
        assert isinstance(run_id, int)
        assert run_id >= 1

    def test_multiple_runs_increment_id(self, audit):
        id1 = audit.log_run("r.sql", {}, "alice", 10, "success")
        id2 = audit.log_run("r.sql", {}, "bob", 20, "success")
        assert id2 > id1

    def test_error_status_stored(self, audit):
        audit.log_run("r.sql", {}, "alice", 0, "error", "timeout")
        runs = audit.get_runs()
        assert runs[0]["status"] == "error"
        assert runs[0]["error"] == "timeout"

    def test_params_stored_as_json(self, audit):
        audit.log_run("r.sql", {"date": "2024-01-01"}, "alice", 5, "success")
        runs = audit.get_runs()
        assert "2024-01-01" in runs[0]["params"]


class TestLogSignoff:
    def test_returns_integer_id(self, audit):
        run_id = audit.log_run("r.sql", {}, "alice", 1, "success")
        so_id = audit.log_signoff(run_id, "r.sql", "bob", "Looks good")
        assert isinstance(so_id, int)

    def test_signoff_stored(self, audit):
        run_id = audit.log_run("r.sql", {}, "alice", 1, "success")
        audit.log_signoff(run_id, "r.sql", "bob", "OK")
        signoffs = audit.get_signoffs()
        assert signoffs[0]["signed_off_by"] == "bob"
        assert signoffs[0]["notes"] == "OK"


class TestGetRuns:
    def test_empty_initially(self, audit):
        assert audit.get_runs() == []

    def test_returns_most_recent_first(self, audit):
        audit.log_run("a.sql", {}, "u", 1, "success")
        audit.log_run("b.sql", {}, "u", 2, "success")
        runs = audit.get_runs()
        # More recent (higher id) should come first
        assert runs[0]["id"] > runs[1]["id"]

    def test_limit_respected(self, audit):
        for i in range(5):
            audit.log_run(f"r{i}.sql", {}, "u", i, "success")
        assert len(audit.get_runs(limit=3)) == 3


class TestGetSignoffs:
    def test_empty_initially(self, audit):
        assert audit.get_signoffs() == []


class TestAggPersist:
    def _persist(self, audit, name="my_agg"):
        return audit.log_agg_persist(
            name=name,
            report_path="r.sql",
            run_id=1,
            group_by=["FLAVOUR"],
            value_cols={"UNITS_SOLD": "sum"},
            row_count=2,
            source_row_count=4,
            size_bytes=1024,
            storage_path="/tmp/my_agg.json",
        )

    def test_returns_integer_id(self, audit):
        assert isinstance(self._persist(audit), int)

    def test_stored_and_retrievable(self, audit):
        self._persist(audit, "agg_a")
        items = audit.get_agg_persists()
        assert len(items) == 1
        assert items[0]["name"] == "agg_a"
        assert items[0]["row_count"] == 2
        assert items[0]["size_bytes"] == 1024

    def test_duplicate_name_raises(self, audit):
        self._persist(audit, "dup")
        with pytest.raises(Exception):
            self._persist(audit, "dup")

    def test_empty_initially(self, audit):
        assert audit.get_agg_persists() == []

    def test_most_recent_first(self, audit):
        self._persist(audit, "first")
        self._persist(audit, "second")
        items = audit.get_agg_persists()
        assert items[0]["name"] == "second"
