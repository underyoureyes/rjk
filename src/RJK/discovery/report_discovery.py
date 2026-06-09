from pathlib import Path

from RJK.parser.sql_metadata_parser import parse_sql_metadata


def discover_reports(reports_root: Path) -> list[dict]:
    """Walk the reports directory and return a flat list of reports with metadata."""
    reports = []
    for sql_file in sorted(reports_root.rglob("*.sql")):
        rel_path = sql_file.relative_to(reports_root).as_posix()
        meta = parse_sql_metadata(sql_file)
        reports.append({
            "path": rel_path,
            "title": meta.get("title", sql_file.stem),
            "description": meta.get("description", ""),
            "owner": meta.get("owner", ""),
            "tags": meta.get("tags", []),
        })
    return reports


def build_report_tree(reports: list[dict]) -> dict:
    """Convert a flat list of reports into a nested directory tree."""
    tree: dict = {}
    for report in reports:
        parts = report["path"].split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {"_type": "dir", "_children": {}})["_children"]
        node[parts[-1]] = {"_type": "report", **report}
    return tree
