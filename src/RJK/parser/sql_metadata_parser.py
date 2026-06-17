import re
from pathlib import Path

import yaml

_FILE_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def parse_sql_metadata(sql_path: Path) -> dict:
    """Extract metadata from a report file.

    For .sql files: reads the YAML block inside the leading /* ... */ comment.
    For .csv/.xlsx/.xls files: reads the companion <name>.meta.yaml sidecar.
    """
    if sql_path.suffix.lower() in _FILE_EXTENSIONS:
        return _parse_file_metadata(sql_path)

    content = sql_path.read_text(encoding="utf-8")
    match = re.search(r"/\*\s*(.*?)\s*\*/", content, re.DOTALL)
    if not match:
        return {"title": sql_path.stem, "description": "", "params": {}}
    try:
        meta = yaml.safe_load(match.group(1))
        return meta if isinstance(meta, dict) else {}
    except yaml.YAMLError:
        return {}


def _parse_file_metadata(file_path: Path) -> dict:
    """Read the .meta.yaml sidecar for an uploaded CSV/Excel file."""
    sidecar = file_path.parent / (file_path.name + ".meta.yaml")
    base = {"title": file_path.stem, "description": "", "params": {}, "source": "upload"}
    if not sidecar.exists():
        return base
    try:
        meta = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
        return {**base, **(meta if isinstance(meta, dict) else {})}
    except yaml.YAMLError:
        return base


def extract_sql(content: str) -> str:
    """Strip the leading metadata comment and return the bare SQL."""
    return re.sub(r"/\*.*?\*/", "", content, count=1, flags=re.DOTALL).strip()
