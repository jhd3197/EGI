"""Operation-alert routes (plan-11 §3).

Broadcasting an alert is a commander-level action; viewing past alerts and their
per-message delivery status is viewer-level. Delivery detail for one alert reuses
the unified message log filtered by ``alert_id``.
"""

from fastapi import APIRouter, Depends

from auth import require_commander, require_viewer
from models import AlertCreate
from modules import alerts, messaging
from ratelimit import rate_limit

router = APIRouter()


@router.post("/operations/{op_id}/alerts", dependencies=[Depends(rate_limit)])
def create_alert(op_id: str, req: AlertCreate, principal: str = Depends(require_commander)):
    return alerts.create_alert(op_id, req, actor=principal)


@router.get("/operations/{op_id}/alerts")
def list_alerts(op_id: str, principal: str = Depends(require_viewer)):
    return alerts.list_alerts(op_id)


@router.get("/alerts/{alert_id}/messages")
def alert_messages(alert_id: str, principal: str = Depends(require_viewer)):
    return messaging.list_messages(alert_id=alert_id, limit=1000)
