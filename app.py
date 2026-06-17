import io
import json
import re
import sys
import uuid
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging

from datetime import datetime, timezone
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from RJK.audit.audit_service import AuditService
from RJK.config.loader import Config
from RJK.discovery.report_discovery import build_report_tree, discover_reports
from RJK.parser.sql_metadata_parser import parse_sql_metadata
from RJK.services.access_service import AccessService, AclConfig, FolderRule, TempUser
from RJK.services.aggregation_service import AggregationService
from RJK.services.chart_service import ChartService, infer_columns
from RJK.services.data_scanner import (
    get_scanner,
    get_scanner_from_path,
    load_scanner_config,
    save_scanner_config,
)
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
access_service = AccessService(config.acl_path, auth_enabled=config.auth_enabled)
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


@app.post("/api/reports/upload")
async def upload_report(
    file: UploadFile = File(...),
    folder: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    owner: str = Form(""),
    tags: str = Form(""),
    uploaded_by: str = Form(""),
):
    import pandas as pd

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Only CSV and Excel (.xlsx/.xls) files are supported")

    # Resolve and validate target directory
    reports_root = Path(config.reports_root).resolve()
    if folder:
        target_dir = (reports_root / folder).resolve()
        if not str(target_dir).startswith(str(reports_root)):
            raise HTTPException(status_code=400, detail="Invalid folder path")
    else:
        target_dir = reports_root
    target_dir.mkdir(parents=True, exist_ok=True)

    # Sanitise filename and write data file
    safe_stem = re.sub(r"[^\w\-]", "_", Path(file.filename).stem)
    data_path  = target_dir / (safe_stem + suffix)
    content    = await file.read()
    data_path.write_bytes(content)

    # Parse to capture row count and columns
    try:
        if suffix == ".csv":
            df = pd.read_csv(data_path, nrows=0)   # headers only for speed
            full_df = pd.read_csv(data_path)
        else:
            df = pd.read_excel(data_path, nrows=0)
            full_df = pd.read_excel(data_path)
        row_count = len(full_df)
        columns   = list(full_df.columns)
    except Exception as exc:
        data_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}")

    # Write sidecar metadata
    meta = {
        "title":             title or Path(file.filename).stem,
        "description":       description,
        "owner":             owner,
        "tags":              [t.strip() for t in tags.split(",") if t.strip()],
        "source":            "upload",
        "original_filename": file.filename,
        "file_size":         len(content),
        "row_count":         row_count,
        "columns":           columns,
        "uploaded_by":       uploaded_by,
        "upload_date":       datetime.now(timezone.utc).isoformat(),
    }
    sidecar = data_path.parent / (data_path.name + ".meta.yaml")
    sidecar.write_text(yaml.dump(meta, default_flow_style=False, allow_unicode=True), encoding="utf-8")

    rel = data_path.relative_to(reports_root).as_posix()
    logger.info("Uploaded report: %s (%d rows, %d bytes)", rel, row_count, len(content))
    return {"path": rel, "row_count": row_count, "columns": columns, "file_size": len(content)}


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
            scan = get_scanner_from_path(config.scanner_config_path).scan_columns(list(result["rows"][0].keys()))
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
    return load_scanner_config(config.scanner_config_path)


@app.get("/api/admin/scanner-config")
def admin_get_scanner_config():
    return load_scanner_config(config.scanner_config_path)


@app.put("/api/admin/scanner-config")
async def admin_put_scanner_config(request: Request):
    body = await request.json()
    cfg = {
        "restricted_keywords": [str(k).lower().strip() for k in body.get("restricted_keywords", []) if k],
        "pii_combination_keywords": [str(k).lower().strip() for k in body.get("pii_combination_keywords", []) if k],
        "pii_combo_threshold": max(1, int(body.get("pii_combo_threshold", 3))),
    }
    save_scanner_config(config.scanner_config_path, cfg)
    return {"ok": True, "saved": cfg}


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

    request_user = access_service.get_current_user(dict(request.headers))
    allowed, reason = access_service.can_create_folder(request_user, folder)
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Access denied: {reason}")

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
    path = (aggs_dir / f"{name}.json").resolve()
    if not str(path).startswith(str(aggs_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid dataset name")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read dataset: {exc}")
    rows = data.get("rows", [])
    meta = {k: v for k, v in data.items() if k != "rows"}
    return {"meta": meta, "columns": infer_columns(rows)}


@app.get("/api/aggs/persisted/{name}/rows")
def get_persisted_agg_rows(name: str):
    aggs_dir = Path(config.audit_db_path).parent / "aggs"
    path = (aggs_dir / f"{name}.json").resolve()
    if not str(path).startswith(str(aggs_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid dataset name")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read dataset: {exc}")
    return {"rows": data.get("rows", [])}


@app.post("/api/aggs/persisted/{name}/access")
def record_agg_access(name: str):
    aggs_dir = Path(config.audit_db_path).parent / "aggs"
    path = (aggs_dir / f"{name}.json").resolve()
    if not str(path).startswith(str(aggs_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid dataset name")
    audit.update_agg_access(name)
    return {"ok": True}


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


@app.post("/api/reporting/chart-raw")
async def chart_raw(request: Request):
    """Generate a chart directly from posted rows — no persisted dataset required."""
    body        = await request.json()
    rows        = body.get("rows", [])
    chart_type  = body.get("chart_type", "bar")
    x           = body.get("x", "")
    y           = body.get("y", "")
    color       = body.get("color") or None
    title       = body.get("title", "")
    show_legend = bool(body.get("show_legend", False))
    if not rows or not x or not y:
        raise HTTPException(status_code=400, detail="rows, x, and y are required")
    try:
        fig = chart_service.build(rows, chart_type, x, y, color, title, show_legend=show_legend)
        return fig
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Chart generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


def _chart_to_png_bytes(fig_dict: dict) -> bytes:
    """Render a Plotly figure dict to PNG bytes via kaleido."""
    import plotly.graph_objects as go
    fig = go.Figure(data=fig_dict.get("data", []), layout=fig_dict.get("layout", {}))
    return fig.to_image(format="png", width=1400, height=700, scale=2)


@app.post("/api/reporting/chart-export/pdf")
async def chart_export_pdf(request: Request):
    body       = await request.json()
    fig_dict   = body.get("fig", {})
    title      = body.get("title", "Chart")
    filename   = (body.get("filename") or "chart") + ".pdf"
    notes_html = (body.get("notes_html") or "").strip()
    try:
        png_bytes = _chart_to_png_bytes(fig_dict)
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Image as RLImage, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_LEFT
        import io as _io
        buf = _io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.5*cm,
                                rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
        styles = getSampleStyleSheet()
        img_buf = _io.BytesIO(png_bytes)
        pw = landscape(A4)[0] - 3*cm
        # Shrink chart slightly if there are notes to leave room
        img_h = pw * 0.42 if notes_html else pw * 0.5
        img = RLImage(img_buf, width=pw, height=img_h)
        story = [Paragraph(title, styles["Title"]), Spacer(1, 0.3*cm), img]
        if notes_html:
            import re as _re
            from reportlab.lib.colors import HexColor
            # Strip tags ReportLab doesn't support; keep b/i/u/br/font/span
            safe = _re.sub(r'<(?!/?(?:b|i|u|br|p|span|font)[>\s/])[^>]+>', ' ', notes_html)
            safe = _re.sub(r'\s+', ' ', safe).strip()
            notes_style = ParagraphStyle("Notes", parent=styles["Normal"],
                                         fontSize=10, leading=14, spaceBefore=0.4*cm,
                                         textColor=HexColor("#333333"), alignment=TA_LEFT)
            story += [Spacer(1, 0.3*cm), Paragraph(safe, notes_style)]
        doc.build(story)
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as exc:
        logger.exception("Chart PDF export failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reporting/chart-export/ppt")
async def chart_export_ppt(request: Request):
    body       = await request.json()
    fig_dict   = body.get("fig", {})
    title      = body.get("title", "Chart")
    filename   = (body.get("filename") or "chart") + ".pptx"
    notes_text = (body.get("notes_text") or "").strip()
    try:
        png_bytes = _chart_to_png_bytes(fig_dict)
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        import io as _io
        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)
        layout = prs.slide_layouts[5]   # blank
        slide = prs.slides.add_slide(layout)
        # Title text box
        txb = slide.shapes.add_textbox(Inches(0.4), Inches(0.15), Inches(12.5), Inches(0.6))
        tf  = txb.text_frame
        tf.text = title
        tf.paragraphs[0].runs[0].font.size  = Pt(24)
        tf.paragraphs[0].runs[0].font.bold  = True
        tf.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x00, 0x30, 0x87)
        # Chart image — shrink to leave room for notes when present
        img_top = Inches(0.85)
        if notes_text:
            img_h    = Inches(4.8)
            notes_h  = Inches(1.5)
            notes_top = Inches(7.5) - notes_h - Inches(0.15)  # pin to bottom of slide
        else:
            img_h    = Inches(6.4)
        img_buf = _io.BytesIO(png_bytes)
        slide.shapes.add_picture(img_buf, Inches(0.2), img_top, Inches(12.9), img_h)
        # Notes text box pinned to bottom of slide
        if notes_text:
            ntxb = slide.shapes.add_textbox(Inches(0.4), notes_top, Inches(12.5), notes_h)
            ntf  = ntxb.text_frame
            ntf.word_wrap = True
            p = ntf.paragraphs[0]
            run = p.add_run()
            run.text = notes_text
            run.font.size  = Pt(11)
            run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        out = _io.BytesIO()
        prs.save(out)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.exception("Chart PPT export failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/about")
def get_about():
    md_path = Path(__file__).parent / "ABOUT.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="ABOUT.md not found")
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


# ---------------------------------------------------------------------------
# Admin — access control
# ---------------------------------------------------------------------------

@app.get("/api/admin/status")
async def admin_status(request: Request):
    username, user_source = access_service.get_current_user_with_source(dict(request.headers))
    user_groups = access_service.get_unix_groups(username)
    cfg = access_service.load_config()
    return {
        "auth_enabled": access_service.auth_enabled,
        "local_run": not access_service.auth_enabled,
        "unix_available": _UNIX_AVAILABLE,
        "current_user": username,
        "user_source": user_source,
        "current_user_groups": user_groups,
        "is_admin": access_service.is_admin(username, user_groups=user_groups, cfg=cfg),
    }


@app.get("/api/admin/config")
def admin_get_config():
    cfg = access_service.load_config()
    return access_service.config_to_dict(cfg)


@app.put("/api/admin/config")
async def admin_save_config(request: Request):
    body = await request.json()
    try:
        rules = []
        for r in body.get("folder_rules", []):
            temp_users = [TempUser(**u) for u in r.get("temp_users", [])]
            rules.append(FolderRule(
                id=r.get("id") or str(uuid.uuid4())[:8],
                folder_pattern=r.get("folder_pattern", "*"),
                description=r.get("description", ""),
                unix_groups=r.get("unix_groups", []),
                temp_users=temp_users,
            ))
        admin_tu = [TempUser(**u) for u in body.get("admin_temp_users", [])]
        cfg = AclConfig(
            folder_rules=rules,
            admin_groups=body.get("admin_groups", []),
            admin_temp_users=admin_tu,
        )
        access_service.save_config(cfg)
        return {"status": "ok", "rules_saved": len(rules)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/unix-groups")
def admin_unix_groups():
    return {"groups": access_service.list_system_groups(), "unix_available": _UNIX_AVAILABLE}


# ---------------------------------------------------------------------------
# Admin — filesystem management (rename / trash)
# ---------------------------------------------------------------------------

def _require_admin(request: Request):
    """Raise 403 if the caller is not an admin."""
    username, _ = access_service.get_current_user_with_source(dict(request.headers))
    user_groups  = access_service.get_unix_groups(username)
    cfg          = access_service.load_config()
    if not access_service.is_admin(username, user_groups=user_groups, cfg=cfg):
        raise HTTPException(status_code=403, detail="Admin access required")


def _safe_path(rel: str) -> Path:
    """Resolve *rel* inside reports_root; raise 400 on traversal attempts."""
    root  = config.reports_root.resolve()
    target = (root / rel).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target


def _trash_dest(src: Path) -> Path:
    """Return the trash destination path, creating parent dirs as needed."""
    import shutil as _sh
    root  = config.reports_root.resolve()
    rel   = src.relative_to(root)
    dest  = root / "_trash" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Avoid overwriting existing trash entries
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix if dest.is_file() else ""
        dest = dest.with_name(stem + f"_{uuid.uuid4().hex[:6]}" + suffix)
    return dest


@app.patch("/api/admin/fs/rename")
async def admin_rename(request: Request):
    _require_admin(request)
    body    = await request.json()
    old_rel = body.get("path", "")
    new_name = (body.get("new_name") or "").strip()
    if not old_rel or not new_name:
        raise HTTPException(status_code=400, detail="path and new_name are required")
    if "/" in new_name or "\\" in new_name or new_name.startswith("."):
        raise HTTPException(status_code=400, detail="new_name must be a plain name with no path separators")

    src = _safe_path(old_rel)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Source not found")

    # For .sql reports keep the .sql extension
    if src.is_file() and not new_name.endswith(".sql"):
        new_name = new_name + ".sql"

    dest = src.parent / new_name
    if dest.exists():
        raise HTTPException(status_code=409, detail=f"'{new_name}' already exists")

    src.rename(dest)
    return {"ok": True, "new_path": str(dest.relative_to(config.reports_root.resolve()))}


@app.delete("/api/admin/fs/report")
async def admin_trash_report(request: Request):
    _require_admin(request)
    body    = await request.json()
    rel     = body.get("path", "")
    if not rel:
        raise HTTPException(status_code=400, detail="path is required")

    import shutil as _sh
    src  = _safe_path(rel)
    if not src.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    if "_trash" in src.parts:
        raise HTTPException(status_code=400, detail="Already in trash")

    dest = _trash_dest(src)
    _sh.move(str(src), str(dest))
    return {"ok": True, "trashed_to": str(dest.relative_to(config.reports_root.resolve()))}


@app.delete("/api/admin/fs/folder")
async def admin_trash_folder(request: Request):
    _require_admin(request)
    body    = await request.json()
    rel     = body.get("path", "")
    if not rel:
        raise HTTPException(status_code=400, detail="path is required")

    import shutil as _sh
    src  = _safe_path(rel)
    if not src.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")
    if "_trash" in src.parts:
        raise HTTPException(status_code=400, detail="Already in trash")

    dest = _trash_dest(src)
    _sh.move(str(src), str(dest))
    return {"ok": True, "trashed_to": str(dest.relative_to(config.reports_root.resolve()))}


try:
    import grp as _grp_check
    _UNIX_AVAILABLE = True
except ImportError:
    _UNIX_AVAILABLE = False
