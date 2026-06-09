import itertools
import random
from pathlib import Path

from RJK.parser.sql_metadata_parser import parse_sql_metadata
from RJK.runners.base import BaseRunner


class MockRunner(BaseRunner):
    """Generates synthetic data from the ``mock`` block in SQL metadata.

    Dimensions are combined via cartesian product; numeric columns are filled
    with random values in the configured range.
    """

    def run(self, sql_path: Path, params: dict) -> list[dict]:
        meta = parse_sql_metadata(sql_path)
        mock_cfg = meta.get("mock", {})
        dimensions: dict[str, list] = mock_cfg.get("dimensions", {})
        numerics: dict[str, dict] = mock_cfg.get("numerics", {})

        if not dimensions:
            return [{"message": "no mock data configured", "path": str(sql_path)}]

        rows = []
        for combo in itertools.product(*dimensions.values()):
            row = dict(zip(dimensions.keys(), combo))
            for col, cfg in numerics.items():
                lo = float(cfg.get("min", 0.0))
                hi = float(cfg.get("max", 1.0))
                decimals = int(cfg.get("decimals", 4))
                if decimals == 0:
                    row[col] = random.randint(int(lo), int(hi))
                else:
                    row[col] = round(random.uniform(lo, hi), decimals)
            rows.append(row)

        return rows
