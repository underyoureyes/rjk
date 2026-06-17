from pathlib import Path

import pandas as pd

from RJK.runners.base import BaseRunner

_SUPPORTED = {".csv", ".xlsx", ".xls"}


class FileRunner(BaseRunner):
    """Reads CSV or Excel uploads and returns rows as a list of dicts."""

    def run(self, sql_path: Path, params: dict, limit: int | None = 2000, **kwargs) -> list[dict]:
        suffix = sql_path.suffix.lower()
        if suffix not in _SUPPORTED:
            raise ValueError(f"Unsupported file type: {suffix}")

        if suffix == ".csv":
            df = pd.read_csv(sql_path, dtype=str)
        else:
            df = pd.read_excel(sql_path, dtype=str)

        # Coerce numeric-looking columns back to numbers for ag-Grid sorting/charting
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass

        if limit:
            df = df.head(limit)

        return df.where(pd.notnull(df), None).to_dict(orient="records")
