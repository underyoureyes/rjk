import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from RJK.audit.audit_service import AuditService
from RJK.config.loader import Config
from RJK.discovery.report_discovery import build_report_tree, discover_reports
from RJK.parser.sql_metadata_parser import parse_sql_metadata
from RJK.services.aggregation_service import AggregationService
from RJK.services.export_service import ExportService
from RJK.services.report_service import ReportService
from RJK.ui.layout import get_index_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

config = Config()
for warning in config.validate():
    logger.warning(warning)

audit = AuditService(config.audit_db_path)
report_service = ReportService(config, audit)
export_service = ExportService()
agg_service = AggregationService()

app = FastAPI(title="RJK Reporting Framework", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def root():
    return get_index_html()


@app.get("/api/reports")
def list_reports():
    reports = discover_reports(config.reports_root)
    tree = build_report_tree(reports)
    return {"reports": reports, "tree": tree}


@app.get("/api/reports/meta")
def get_report_meta(path: str):
    try:
        meta = report_service.get_metadata(path)
        # Strip the mock block from the API response — clients don't need it
        meta_clean = {k: v for k, v in meta.items() if k != "mock"}
        return meta_clean
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/reports/run")
async def run_report(request: Request):
    body = await request.json()
    path = body.get("path")
    params = body.get("params", {})
    run_by = body.get("run_by", "anonymous")
    max_rows = body.get("max_rows")
    max_rows = None if max_rows is None else int(max_rows)
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        result = report_service.run_report(path, params, run_by, max_rows)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Report run failed: %s", path)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reports/aggregate")
async def aggregate_report(request: Request):
    body = await request.json()
    rows = body.get("rows", [])
    group_by = body.get("group_by", [])
    value_cols = body.get("value_cols", {})
    if isinstance(value_cols, list):
        value_cols = {col: "sum" for col in value_cols}
    if not value_cols:
        raise HTTPException(status_code=400, detail="value_cols is required")
    try:
        result = agg_service.preview(rows, group_by, value_cols)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Aggregation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reports/export/csv")
async def export_csv(request: Request):
    body = await request.json()
    path = body.get("path")
    params = body.get("params", {})
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        result = report_service.run_report(path, params)
        csv_bytes = export_service.to_csv(result["rows"])
        filename = Path(path).stem + ".csv"
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/reports/export/excel")
async def export_excel(request: Request):
    body = await request.json()
    path = body.get("path")
    params = body.get("params", {})
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        result = report_service.run_report(path, params)
        excel_bytes = export_service.to_excel(result["rows"], sheet_name=Path(path).stem)
        filename = Path(path).stem + ".xlsx"
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/config/persist-options")
def persist_options():
    return {"mysql_available": bool(config.mysql_url)}


@app.post("/api/aggs/persist")
async def persist_agg(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    rows = body.get("rows", [])
    report_path = body.get("report_path", "")
    run_id = body.get("run_id")
    group_by = body.get("group_by", [])
    value_cols = body.get("value_cols", {})
    source_row_count = body.get("source_row_count", 0)
    fmt = body.get("format", "json")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not report_path:
        raise HTTPException(status_code=400, detail="report_path is required")
    if fmt == "hive":
        raise HTTPException(status_code=501, detail="Hive persistence is not yet implemented — available on Dash Server only")
    if fmt == "mysql":
        if not config.mysql_url:
            raise HTTPException(status_code=400, detail="MYSQL_URL is not configured")
        return await _persist_mysql(name, rows, report_path, run_id, group_by, value_cols, source_row_count)
    # JSON (default)
    return await _persist_json(name, rows, report_path, run_id, group_by, value_cols, source_row_count)


async def _persist_json(name, rows, report_path, run_id, group_by, value_cols, source_row_count):
    aggs_dir = Path(config.audit_db_path).parent / "aggs"
    aggs_dir.mkdir(exist_ok=True)
    payload = {
        "name": name, "report_path": report_path, "run_id": run_id,
        "group_by": group_by, "value_cols": value_cols,
        "row_count": len(rows), "source_row_count": source_row_count,
        "rows": rows,
    }
    json_str = json.dumps(payload, default=str)
    size_bytes = len(json_str.encode("utf-8"))
    storage_path = str(aggs_dir / f"{name}.json")
    try:
        Path(storage_path).write_text(json_str, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {exc}")
    try:
        store_id = audit.log_agg_persist(
            name=name, report_path=report_path, run_id=run_id,
            group_by=group_by, value_cols=value_cols,
            row_count=len(rows), source_row_count=source_row_count,
            size_bytes=size_bytes, storage_path=storage_path, fmt="json",
        )
    except Exception as exc:
        Path(storage_path).unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=str(exc))
    return {"id": store_id, "name": name, "size_bytes": size_bytes, "path": storage_path}


async def _persist_mysql(name, rows, report_path, run_id, group_by, value_cols, source_row_count):
    try:
        import pandas as pd
        from sqlalchemy import create_engine, text
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"sqlalchemy/pymysql not installed: {exc}")
    try:
        engine = create_engine(config.mysql_url)
        df = pd.DataFrame(rows)
        # Estimate size from JSON representation
        size_bytes = len(json.dumps(rows, default=str).encode("utf-8"))
        with engine.begin() as conn:
            # Fail if table already exists to match JSON duplicate behaviour
            exists = conn.execute(
                text("SELECT COUNT(*) FROM information_schema.tables "
                     "WHERE table_schema = DATABASE() AND table_name = :t"),
                {"t": name},
            ).scalar()
            if exists:
                raise HTTPException(status_code=409, detail=f"MySQL table '{name}' already exists")
        df.to_sql(name, engine, if_exists="fail", index=False)
        storage_path = f"mysql:{name}"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MySQL write failed: {exc}")
    try:
        store_id = audit.log_agg_persist(
            name=name, report_path=report_path, run_id=run_id,
            group_by=group_by, value_cols=value_cols,
            row_count=len(rows), source_row_count=source_row_count,
            size_bytes=size_bytes, storage_path=storage_path, fmt="mysql",
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"id": store_id, "name": name, "size_bytes": size_bytes, "path": storage_path}


@app.get("/api/aggs/persisted")
def list_persisted_aggs(limit: int = 100):
    return {"items": audit.get_agg_persists(limit)}


@app.get("/api/about")
def get_about():
    md_path = Path(__file__).parent / "CLAUDE.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="CLAUDE.md not found")
    return {"content": md_path.read_text(encoding="utf-8")}


@app.get("/api/audit")
def get_audit(limit: int = 200):
    return {
        "runs": audit.get_runs(limit),
        "signoffs": audit.get_signoffs(limit),
    }


@app.post("/api/signoff")
async def signoff(request: Request):
    body = await request.json()
    run_id = body.get("run_id")
    report_path = body.get("report_path")
    signed_off_by = body.get("signed_off_by", "anonymous")
    notes = body.get("notes", "")
    params = body.get("params")
    if not run_id or not report_path:
        raise HTTPException(status_code=400, detail="run_id and report_path are required")
    signoff_id = audit.log_signoff(int(run_id), report_path, signed_off_by, notes, params)
    return {"signoff_id": signoff_id, "status": "ok"}
