import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    db_conn_string: str = field(default_factory=lambda: os.getenv("DB_CONN_STRING", ""))
    reports_root: Path = field(default_factory=lambda: Path(os.getenv("REPORTS_ROOT", "reports")))
    audit_db_path: Path = field(default_factory=lambda: Path(os.getenv("AUDIT_DB_PATH", "data/audit.db")))
    mock_mode: bool = field(default_factory=lambda: os.getenv("MOCK_MODE", "true").lower() == "true")

    def validate(self) -> list[str]:
        warnings = []
        if not self.mock_mode and not self.db_conn_string:
            warnings.append("DB_CONN_STRING not set; falling back to mock mode")
        if not self.reports_root.exists():
            warnings.append(f"REPORTS_ROOT not found: {self.reports_root}")
        return warnings


config = Config()
