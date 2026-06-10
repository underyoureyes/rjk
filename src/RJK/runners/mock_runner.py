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


def _generate_date_range(cfg: dict) -> list[str]:
    """Expand a date_range spec into a list of formatted date strings.

    cfg keys:
      start  – date expr, e.g. 'today-730'
      end    – date expr, e.g. 'today'
      freq   – 'daily' | 'weekday' (Mon-Fri) | 'weekly' (Fridays) | 'monthly'
    """
    start = _parse_date(_resolve_date_expr(str(cfg.get("start", "today"))))
    end   = _parse_date(_resolve_date_expr(str(cfg.get("end",   "today"))))
    freq  = cfg.get("freq", "daily")
    if not start or not end:
        return []

    dates, cur = [], start
    while cur <= end:
        wd = cur.weekday()  # 0=Mon … 6=Sun
        include = (
            freq == "daily"    or
            (freq == "weekday" and wd < 5) or
            (freq == "weekly"  and wd == 4) or   # Fridays
            (freq == "monthly" and cur.day == 1)
        )
        if include:
            dates.append(cur.strftime(_FMT))
        if freq == "monthly":
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            cur += timedelta(days=1)
    return dates


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

    def run(self, sql_path: Path, params: dict, limit: int | None = 2000) -> list[dict]:
        meta = parse_sql_metadata(sql_path)
        mock_cfg = meta.get("mock", {})
        dimensions: dict[str, list] = mock_cfg.get("dimensions", {})
        numerics: dict[str, dict] = mock_cfg.get("numerics", {})
        filters: dict[str, dict] = mock_cfg.get("filters", {})
        derived: dict[str, dict] = mock_cfg.get("derived", {})

        if not dimensions:
            return [{"message": "no mock data configured", "path": str(sql_path)}]

        resolved = {}
        for k, vals in dimensions.items():
            if isinstance(vals, dict) and "date_range" in vals:
                resolved[k] = _generate_date_range(vals["date_range"])
            else:
                resolved[k] = [_resolve_date_expr(str(v)) for v in vals]

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
            for col_name, col_cfg in derived.items():
                src = col_cfg.get("month_start_of")
                if src and src in row:
                    d = _parse_date(str(row[src]))
                    row[col_name] = d.replace(day=1).strftime(_FMT) if d else None
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

        return rows if limit is None else rows[:limit]
