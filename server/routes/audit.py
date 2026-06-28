"""Consolidated audit log endpoint (plan-15 §5.3).

Thin HTTP adapter over ``modules.audit.query_log`` that exposes the operator
action trail (``audit_log``) and the per-record change trail (``record_history``)
through a single, filterable, operator-gated endpoint. ``?format=export`` streams
the same result as a downloadable JSON file for long-term retention.

Operator-gated: the audit trail names principals and actions, so it is not
public; it sits at the same trust level as the moderation surface.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from auth import require_operator
from modules import audit

router = APIRouter()


@router.get("/audit/log")
def audit_log(
    source: str = Query("all", pattern="^(all|actions|history)$"),
    actor: str = Query(None),
    action: str = Query(None),
    target_type: str = Query(None),
    person_id: str = Query(None),
    since: str = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    fmt: str = Query("json", alias="format", pattern="^(json|export)$"),
    principal: str = Depends(require_operator),
):
    result = audit.query_log(
        source=source,
        actor=actor,
        action=action,
        target_type=target_type,
        person_id=person_id,
        since=since,
        limit=limit,
        offset=offset,
    )
    if fmt == "export":
        return JSONResponse(
            content=result,
            headers={
                "Content-Disposition": 'attachment; filename="egi-audit-log.json"'
            },
        )
    return result
