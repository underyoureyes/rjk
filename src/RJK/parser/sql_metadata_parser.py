import re
from pathlib import Path

import yaml


def parse_sql_metadata(sql_path: Path) -> dict:
    """Extract the YAML metadata block from the /* ... */ comment at the top of a SQL file."""
    content = sql_path.read_text(encoding="utf-8")
    match = re.search(r"/\*\s*(.*?)\s*\*/", content, re.DOTALL)
    if not match:
        return {"title": sql_path.stem, "description": "", "params": {}}
    try:
        meta = yaml.safe_load(match.group(1))
        return meta if isinstance(meta, dict) else {}
    except yaml.YAMLError:
        return {}


def extract_sql(content: str) -> str:
    """Strip the leading metadata comment and return the bare SQL."""
    return re.sub(r"/\*.*?\*/", "", content, count=1, flags=re.DOTALL).strip()
