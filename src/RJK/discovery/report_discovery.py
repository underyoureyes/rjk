from pathlib import Path

from RJK.parser.sql_metadata_parser import parse_sql_metadata

_REPORT_GLOBS = ["**/*.sql", "**/*.csv", "**/*.xlsx", "**/*.xls"]


def discover_reports(reports_root: Path) -> list[dict]:
    """Walk the reports directory and return a flat list of reports with metadata."""
    seen: set[Path] = set()
    candidates: list[Path] = []
    for pattern in _REPORT_GLOBS:
        for f in reports_root.glob(pattern):
            if f not in seen:
                seen.add(f)
                candidates.append(f)

    reports = []
    for report_file in sorted(candidates):
        # Skip sidecar metadata files and anything in _trash
        if report_file.name.endswith(".meta.yaml"):
            continue
        if "_trash" in report_file.parts:
            continue
        rel_path = report_file.relative_to(reports_root).as_posix()
        meta = parse_sql_metadata(report_file)
        entry = {
            "path":        rel_path,
            "title":       meta.get("title", report_file.stem),
            "description": meta.get("description", ""),
            "owner":       meta.get("owner", ""),
            "tags":        meta.get("tags", []),
            "source":      meta.get("source", "sql"),
        }
        # Carry upload-specific fields so the tree popover can display them
        for field in ("row_count", "file_size", "uploaded_by", "upload_date", "original_filename"):
            if field in meta:
                entry[field] = meta[field]
        reports.append(entry)
    return reports


def build_report_tree(reports: list[dict]) -> dict:
    """Convert a flat list of reports into a nested directory tree."""
    tree: dict = {}
    for report in reports:
        parts = report["path"].split("/")
        node = tree
        accumulated = []
        for part in parts[:-1]:
            accumulated.append(part)
            dir_node = node.setdefault(part, {"_type": "dir", "_path": "/".join(accumulated), "_children": {}})
            dir_node["_path"] = "/".join(accumulated)
            node = dir_node["_children"]
        node[parts[-1]] = {"_type": "report", **report}
    return tree
