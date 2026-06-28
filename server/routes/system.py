"""System events + migration status endpoints (plan-15 §11, §7).

Operator-gated read surface over ``system_events`` (what the server did to
itself) plus a migration-status probe so an operator can confirm the schema is
up to date without shelling into the box.
"""

from fastapi import APIRouter, Depends, Query

from auth import require_operator
from modules import system_events

router = APIRouter()


@router.get("/system/events")
def list_system_events(
    level: str = Query(None, pattern="^(info|warning|error)$"),
    event_type: str = Query(None),
    since: str = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    principal: str = Depends(require_operator),
):
    return system_events.list_events(
        level=level, event_type=event_type, since=since, limit=limit, offset=offset
    )


@router.get("/system/migrations")
def migration_status(principal: str = Depends(require_operator)):
    """Report applied vs. pending migrations (plan-15 §7.3)."""
    import migrate

    pending = [{"version": v, "file": p.name} for v, p in migrate.pending()]
    return {
        "up_to_date": len(pending) == 0,
        "pending": pending,
        "all": [v for v, _ in migrate.discover()],
    }
