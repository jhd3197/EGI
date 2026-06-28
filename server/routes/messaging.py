"""Communications-hub routes (plan-11): unified message log, send, providers.

Channel-specific endpoints live in their own routers (sms, push, alerts); this
router is the cross-channel surface: list the unified message log, send a single
sms/email, post a delivery-status callback, and manage pluggable providers.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth import require_admin, require_operator, require_viewer
from models import (
    MessageStatusUpdate, ProviderConfig, SendMessageRequest,
)
from modules import messaging
from ratelimit import rate_limit

router = APIRouter()


@router.get("/messages")
def list_messages(
    operation_id: Optional[str] = Query(None),
    person_id: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    alert_id: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    principal: str = Depends(require_viewer),
):
    return messaging.list_messages(
        operation_id=operation_id, person_id=person_id, channel=channel,
        direction=direction, status=status, alert_id=alert_id, limit=limit,
    )


@router.post("/messages", dependencies=[Depends(rate_limit)])
def send_message(req: SendMessageRequest, principal: str = Depends(require_operator)):
    return messaging.send_message(req, actor=principal)


@router.post("/messages/{message_id}/status")
def update_message_status(
    message_id: str, req: MessageStatusUpdate, principal: str = Depends(require_operator)
):
    return messaging.update_status(
        message_id, req.status, external_id=req.external_id, error=req.error,
        actor=principal,
    )


# ── Pluggable providers (admin) ──────────────────────────────────────────────

@router.get("/message-providers")
def list_providers(
    channel: Optional[str] = Query(None), principal: str = Depends(require_operator)
):
    return messaging.list_providers(channel=channel)


@router.post("/message-providers")
def create_provider(req: ProviderConfig, principal: str = Depends(require_admin)):
    return messaging.create_provider(req, actor=principal)


@router.delete("/message-providers/{provider_id}")
def delete_provider(provider_id: str, principal: str = Depends(require_admin)):
    return messaging.delete_provider(provider_id, actor=principal)
