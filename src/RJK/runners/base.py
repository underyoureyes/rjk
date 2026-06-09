from abc import ABC, abstractmethod
from pathlib import Path


class BaseRunner(ABC):
    @abstractmethod
    def run(self, sql_path: Path, params: dict, limit: int | None = None) -> list[dict]:
        """Execute the report and return rows as a list of dicts."""
