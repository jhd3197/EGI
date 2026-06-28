"""SITREP generation + scheduled-report routes (plan-13 §3 Reports).

On-demand SITREP for an operation in json/html/pdf, plus operator-managed
scheduled reports. Generating a SITREP is viewer-gated (read-only situational
awareness); managing schedules and triggering a run mutate state and are
operator-gated.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from auth import require_operator, require_viewer
from models import ScheduledReportCreate, ScheduledReportUpdate
from modules import scheduled_reports, sitrep

router = APIRouter()


@router.get("/operations/{op_id}/sitrep")
def operation_sitrep(
    op_id: str,
    format: str = Query("json", pattern="^(json|html|pdf)$"),
    principal: str = Depends(require_viewer),
):
    if format == "json":
        return sitrep.generate(op_id, "json")
    if format == "html":
        return HTMLResponse(sitrep.generate(op_id, "html"))
    # pdf
    try:
        pdf = sitrep.generate(op_id, "pdf")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    name = op_id
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="sitrep-{name}.pdf"'},
    )


# ── Scheduled reports CRUD (operator) ────────────────────────────────────────

@router.get("/reports/scheduled")
def list_scheduled(operator: str = Depends(require_operator)):
    return scheduled_reports.list_reports()


@router.post("/reports/scheduled")
def create_scheduled(req: ScheduledReportCreate, operator: str = Depends(require_operator)):
    return scheduled_reports.create_report(
        operation_id=req.operation_id,
        name=req.name,
        fmt=req.format or "html",
        schedule_cron=req.schedule_cron or "daily",
        recipients=req.recipients or "",
        actor=operator,
    )


@router.get("/reports/scheduled/{report_id}")
def get_scheduled(report_id: str, operator: str = Depends(require_operator)):
    return scheduled_reports.get_report(report_id)


@router.patch("/reports/scheduled/{report_id}")
def update_scheduled(
    report_id: str, req: ScheduledReportUpdate, operator: str = Depends(require_operator)
):
    if req.active is None:
        return scheduled_reports.get_report(report_id)
    return scheduled_reports.set_active(report_id, req.active, actor=operator)


@router.delete("/reports/scheduled/{report_id}")
def delete_scheduled(report_id: str, operator: str = Depends(require_operator)):
    return scheduled_reports.delete_report(report_id, actor=operator)


@router.post("/reports/scheduled/{report_id}/run")
def run_scheduled(report_id: str, operator: str = Depends(require_operator)):
    """Trigger one scheduled report immediately (manual run)."""
    return scheduled_reports.run_report(scheduled_reports.get_report(report_id))


@router.post("/reports/run-due")
def run_due(operator: str = Depends(require_operator)):
    """Run every active, due scheduled report (manual trigger of the cron job)."""
    return scheduled_reports.run_due()
