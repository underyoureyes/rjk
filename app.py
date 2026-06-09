import io
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
agg_service = AggregationService(report_service)

app = FastAPI(title="RJK Report Framework", version="1.0.0")


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
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        result = report_service.run_report(path, params, run_by)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Report run failed: %s", path)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reports/aggregate")
async def aggregate_report(request: Request):
    body = await request.json()
    path = body.get("path")
    params = body.get("params", {})
    group_by = body.get("group_by", [])
    value_cols = body.get("value_cols") or ([body.get("value_col")] if body.get("value_col") else [])
    agg_func = body.get("agg_func", "sum")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    if not value_cols:
        raise HTTPException(status_code=400, detail="value_cols is required")
    try:
        result = agg_service.preview(path, params, group_by, value_cols, agg_func)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Aggregation failed: %s", path)
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
