from pathlib import Path

from RJK.audit.audit_service import AuditService
from RJK.config.loader import Config
from RJK.parser.sql_metadata_parser import parse_sql_metadata
from RJK.runners.base import BaseRunner
from RJK.runners.mock_runner import MockRunner
from RJK.runners.odbc_runner import OdbcRunner


class ReportService:
    def __init__(self, config: Config, audit: AuditService) -> None:
        self.config = config
        self.audit = audit
        self.runner: BaseRunner = self._pick_runner()

    def _pick_runner(self) -> BaseRunner:
        if self.config.mock_mode or not self.config.db_conn_string:
            return MockRunner()
        return OdbcRunner(self.config.db_conn_string)

    def _resolve_path(self, report_path: str) -> Path:
        sql_path = self.config.reports_root / report_path
        if not sql_path.exists():
            raise FileNotFoundError(f"Report not found: {report_path}")
        return sql_path

    def get_metadata(self, report_path: str) -> dict:
        return parse_sql_metadata(self._resolve_path(report_path))

    def run_report(
        self,
        report_path: str,
        params: dict,
        run_by: str = "anonymous",
        limit: int | None = 2000,
        conn_string: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> dict:
        sql_path = self._resolve_path(report_path)
        try:
            if conn_string:
                runner: BaseRunner = OdbcRunner(conn_string)
                rows = runner.run(sql_path, params, limit,
                                  conn_string=conn_string, username=username, password=password)
            else:
                rows = self.runner.run(sql_path, params, limit)
            run_id = self.audit.log_run(report_path, params, run_by, len(rows), "success")
            return {"run_id": run_id, "rows": rows, "row_count": len(rows)}
        except Exception as exc:
            self.audit.log_run(report_path, params, run_by, 0, "error", str(exc))
            raise
