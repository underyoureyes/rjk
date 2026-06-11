import io
import json
import re
import sys
import yaml
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
from RJK.services.chart_service import ChartService, infer_columns
from RJK.services.data_scanner import get_scanner
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
chart_service = ChartService(geojson_cache_dir=Path(config.audit_db_path).parent / "geojson")

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
    body        = await request.json()
    path        = body.get("path")
    params      = body.get("params", {})
    run_by      = body.get("run_by", "anonymous")
    max_rows    = body.get("max_rows")
    conn_string = body.get("conn_string") or None
    username    = body.get("username") or None
    password    = body.get("password") or None
    max_rows = None if max_rows is None else int(max_rows)
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        result = report_service.run_report(
            path, params, run_by, max_rows,
            conn_string=conn_string, username=username, password=password,
        )
        # Scan columns for sensitive data and attach result
        if result["rows"]:
            scan = get_scanner().scan_columns(list(result["rows"][0].keys()))
            result["scan"] = {
                "clean": scan.clean,
                "flags": [{"column": f.column, "reason": f.reason, "severity": f.severity} for f in scan.flags],
                "summary": scan.summary(),
            }
        else:
            result["scan"] = {"clean": True, "flags": [], "summary": "No data returned."}
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


@app.post("/api/reports/export/pdf")
async def export_pdf(request: Request):
    body = await request.json()
    rows     = body.get("rows", [])
    title    = body.get("title", "Report")
    params   = body.get("params", "")
    filename = body.get("filename", "report") + ".pdf"
    try:
        data = export_service.to_pdf(rows, title=title, params=params)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/reports/export/ppt")
async def export_ppt(request: Request):
    body = await request.json()
    rows     = body.get("rows", [])
    title    = body.get("title", "Report")
    params   = body.get("params", "")
    filename = body.get("filename", "report") + ".pptx"
    try:
        data = export_service.to_ppt(rows, title=title, params=params)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/reports/scan-config")
def scan_config():
    from RJK.services.data_scanner import RESTRICTED_KEYWORDS, PII_COMBINATION_KEYWORDS, PII_COMBO_THRESHOLD
    return {
        "restricted_keywords": RESTRICTED_KEYWORDS,
        "pii_combination_keywords": PII_COMBINATION_KEYWORDS,
        "pii_combo_threshold": PII_COMBO_THRESHOLD,
    }


@app.post("/api/reports/create")
async def create_report(request: Request):
    body        = await request.json()
    folder      = (body.get("folder") or "").strip().strip("/")
    name        = (body.get("name") or "").strip()
    title       = (body.get("title") or name).strip()
    description = (body.get("description") or "").strip()
    owner       = (body.get("owner") or "").strip()
    conn_string = (body.get("conn_string") or "").strip()
    sql_text    = (body.get("sql") or "").strip()

    if not folder:
        raise HTTPException(status_code=400, detail="folder is required")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not sql_text:
        raise HTTPException(status_code=400, detail="sql is required")

    safe_name = re.sub(r"[^\w\-]", "_", name).lower()
    if not safe_name.endswith(".sql"):
        safe_name += ".sql"

    report_dir  = config.reports_root / folder
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / safe_name
    if report_file.exists():
        raise HTTPException(status_code=409, detail=f"Report already exists: {folder}/{safe_name}")

    detected_params = list(dict.fromkeys(re.findall(r":([a-zA-Z_]\w*)", sql_text)))

    meta: dict = {"title": title}
    if description:
        meta["description"] = description
    if owner:
        meta["owner"] = owner
    if conn_string:
        meta["connection"] = {"conn_string": conn_string}
    if detected_params:
        meta["params"] = {
            p: {"type": "text", "label": p.replace("_", " ").title(), "default": ""}
            for p in detected_params
        }

    yaml_block   = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False)
    file_content = f"/*\n{yaml_block}*/\n\n{sql_text}\n"
    report_file.write_text(file_content, encoding="utf-8")

    report_path = str(Path(folder) / safe_name).replace("\\", "/")
    logger.info("Created new report: %s", report_path)
    return {"path": report_path, "filename": safe_name, "folder": folder}


@app.post("/api/reports/test-connection")
async def test_odbc_connection(request: Request):
    body        = await request.json()
    conn_string = (body.get("conn_string") or "").strip()
    username    = (body.get("username") or "").strip()
    password    = (body.get("password") or "").strip()
    if not conn_string:
        raise HTTPException(status_code=400, detail="conn_string is required")
    try:
        import pyodbc
    except ImportError:
        raise HTTPException(status_code=500, detail="pyodbc is not installed on this server")
    try:
        kwargs: dict = {}
        if username:
            kwargs["uid"] = username
        if password:
            kwargs["pwd"] = password
        conn = pyodbc.connect(conn_string, timeout=10, **kwargs)
        conn.close()
        return {"status": "ok", "message": "Connection successful"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}")


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
    persisted_by = (body.get("persisted_by") or "").strip() or None
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not report_path:
        raise HTTPException(status_code=400, detail="report_path is required")
    if fmt == "hive":
        raise HTTPException(status_code=501, detail="Hive persistence is not yet implemented — available on Dash Server only")
    if fmt == "mysql":
        if not config.mysql_url:
            raise HTTPException(status_code=400, detail="MYSQL_URL is not configured")
        return await _persist_mysql(name, rows, report_path, run_id, group_by, value_cols, source_row_count, persisted_by)
    # JSON (default)
    return await _persist_json(name, rows, report_path, run_id, group_by, value_cols, source_row_count, persisted_by)


async def _persist_json(name, rows, report_path, run_id, group_by, value_cols, source_row_count, persisted_by=None):
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
            persisted_by=persisted_by,
        )
    except Exception as exc:
        Path(storage_path).unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=str(exc))
    return {"id": store_id, "name": name, "size_bytes": size_bytes, "path": storage_path}


async def _persist_mysql(name, rows, report_path, run_id, group_by, value_cols, source_row_count, persisted_by=None):
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
            persisted_by=persisted_by,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"id": store_id, "name": name, "size_bytes": size_bytes, "path": storage_path}


@app.get("/api/aggs/persisted")
def list_persisted_aggs(limit: int = 100):
    return {"items": audit.get_agg_persists(limit)}


@app.get("/api/aggs/persisted/{name}")
def get_persisted_agg(name: str):
    aggs_dir = Path(config.audit_db_path).parent / "aggs"
    path = aggs_dir / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read dataset: {exc}")
    rows = data.get("rows", [])
    meta = {k: v for k, v in data.items() if k != "rows"}
    return {"meta": meta, "columns": infer_columns(rows)}


@app.post("/api/reporting/chart")
async def generate_chart(request: Request):
    body = await request.json()
    dataset = (body.get("dataset") or "").strip()
    chart_type  = body.get("chart_type", "bar")
    x           = body.get("x", "")
    y           = body.get("y", "")
    color       = body.get("color") or None
    title       = body.get("title", "")
    show_legend = bool(body.get("show_legend", False))
    if not dataset or not x or not y:
        raise HTTPException(status_code=400, detail="dataset, x, and y are required")
    aggs_dir = Path(config.audit_db_path).parent / "aggs"
    path = aggs_dir / f"{dataset}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset}' not found")
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("rows", [])
        fig = chart_service.build(rows, chart_type, x, y, color, title, show_legend=show_legend)
        return fig
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Chart generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


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
