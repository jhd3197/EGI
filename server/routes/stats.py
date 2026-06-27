"""Dashboard statistics routes (plan-13 §3).

Thin HTTP adapters over ``modules.stats``. All read-only and viewer-gated, like
the rest of the operations surface — a commander/viewer needs situational
awareness, not write access.

NOTE: ``/stats/global`` is a literal path and ``/stats/operations/{id}`` carries
a path parameter; they don't collide, but this router is included after the
operations/geo routers and before the SPA catch-all (see main.py).
"""

from fastapi import APIRouter, Depends, Query

from auth import require_role
from modules import stats

router = APIRouter()

require_viewer = require_role("viewer")


@router.get("/stats/global")
def global_stats(principal: str = Depends(require_viewer)):
    # TTL-cached: global_stats() runs an O(n) duplicate-cluster pass (plan-15 §8.3).
    return stats.cached("global", stats.global_stats)


@router.get("/stats/operations/{op_id}")
def operation_stats(op_id: str, principal: str = Depends(require_viewer)):
    return stats.operation_stats(op_id)


@router.get("/stats/operations/{op_id}/timeseries")
def operation_timeseries(
    op_id: str,
    days: int = Query(30, ge=1, le=365),
    principal: str = Depends(require_viewer),
):
    return stats.operation_timeseries(op_id, days=days)
