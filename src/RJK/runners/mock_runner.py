import itertools
import re
import random
from datetime import datetime, timedelta
from pathlib import Path

from RJK.parser.sql_metadata_parser import parse_sql_metadata
from RJK.runners.base import BaseRunner

_DATE_FMTS = ("%d-%b-%Y", "%Y-%m-%d")
_FMT = "%d-%b-%Y"
_TODAY = lambda: datetime.now().strftime(_FMT)

_REL_DATE = re.compile(r"^today([+-])(\d+)$", re.IGNORECASE)


def _resolve_date_expr(val: str) -> str:
    """Resolve 'today', 'today-N', 'today+N' to a formatted date string."""
    s = val.strip()
    if s.lower() == "today":
        return datetime.now().strftime(_FMT)
    m = _REL_DATE.match(s)
    if m:
        sign, n = m.group(1), int(m.group(2))
        delta = timedelta(days=n if sign == "+" else -n)
        return (datetime.now() + delta).strftime(_FMT)
    return val


def _parse_date(val: str):
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _date_cmp(op: str):
    def cmp(a: str, b: str) -> bool:
        da, db = _parse_date(a), _parse_date(b)
        if da is not None and db is not None:
            if op == "=":  return da == db
            if op == "<=": return da <= db
            if op == ">=": return da >= db
            if op == "<":  return da < db
            if op == ">":  return da > db
        return {"=": a == b, "<=": a <= b, ">=": a >= b, "<": a < b, ">": a > b}.get(op, False)
    return cmp


_OPS = {op: _date_cmp(op) for op in ("=", "<=", ">=", "<", ">")}


class MockRunner(BaseRunner):
    """Generates synthetic data from the ``mock`` block in SQL metadata.

    Dimensions are combined via cartesian product; numeric columns are filled
    with random values in the configured range.  A ``filters`` map in the mock
    block can restrict rows by param value, e.g.:

        filters:
          run_date:
            column: RUN_DATE
            op: "="
    """

    def run(self, sql_path: Path, params: dict, limit: int = 2000) -> list[dict]:
        meta = parse_sql_metadata(sql_path)
        mock_cfg = meta.get("mock", {})
        dimensions: dict[str, list] = mock_cfg.get("dimensions", {})
        numerics: dict[str, dict] = mock_cfg.get("numerics", {})
        filters: dict[str, dict] = mock_cfg.get("filters", {})

        if not dimensions:
            return [{"message": "no mock data configured", "path": str(sql_path)}]

        resolved = {k: [_resolve_date_expr(str(v)) for v in vals]
                    for k, vals in dimensions.items()}

        rows = []
        for combo in itertools.product(*resolved.values()):
            row = dict(zip(resolved.keys(), combo))
            for col, cfg in numerics.items():
                lo = float(cfg.get("min", 0.0))
                hi = float(cfg.get("max", 1.0))
                if "decimals_min" in cfg or "decimals_max" in cfg:
                    d_lo = int(cfg.get("decimals_min", 1))
                    d_hi = int(cfg.get("decimals_max", 8))
                    decimals = random.randint(d_lo, d_hi)
                else:
                    decimals = int(cfg.get("decimals", 4))
                if decimals == 0:
                    row[col] = random.randint(int(lo), int(hi))
                else:
                    row[col] = round(random.uniform(lo, hi), decimals)
            rows.append(row)

        for param_name, f_cfg in filters.items():
            param_val = params.get(param_name)
            if param_val is None:
                continue
            col = f_cfg.get("column")
            op = f_cfg.get("op", "=")
            cmp = _OPS.get(op)
            if not col or not cmp:
                continue
            rows = [r for r in rows if col in r and cmp(str(r[col]), str(param_val))]

        return rows[:limit]
