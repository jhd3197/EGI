"""Outbound webhook routes (plan-12 §3): thin HTTP adapters over modules.webhooks.

Subscriptions are operator-managed server-local configuration, so the whole
router is gated at operator level. Request bodies are local Pydantic models
(precedent: NormalizeRequest in routes/imports.py) to avoid editing models.py.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth import require_operator
from modules import webhooks

router = APIRouter()


class WebhookCreate(BaseModel):
    url: str
    events: str
    secret: Optional[str] = None
    owner_user_id: Optional[str] = None


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[str] = None
    secret: Optional[str] = None
    active: Optional[int] = None


@router.post("/webhooks")
def create_webhook(req: WebhookCreate, principal: str = Depends(require_operator)):
    return webhooks.create_subscription(
        url=req.url, events=req.events, secret=req.secret,
        owner_user_id=req.owner_user_id,
    )


@router.get("/webhooks")
def list_webhooks(principal: str = Depends(require_operator)):
    return webhooks.list_subscriptions()


@router.get("/webhooks/{subscription_id}")
def get_webhook(subscription_id: str, principal: str = Depends(require_operator)):
    return webhooks.get_subscription(subscription_id)


@router.patch("/webhooks/{subscription_id}")
def update_webhook(
    subscription_id: str, req: WebhookUpdate, principal: str = Depends(require_operator)
):
    return webhooks.update_subscription(
        subscription_id, **req.model_dump(exclude_unset=True)
    )


@router.delete("/webhooks/{subscription_id}")
def delete_webhook(subscription_id: str, principal: str = Depends(require_operator)):
    return webhooks.delete_subscription(subscription_id)


@router.get("/webhooks/{subscription_id}/deliveries")
def list_webhook_deliveries(
    subscription_id: str,
    limit: int = Query(100, le=1000),
    principal: str = Depends(require_operator),
):
    return webhooks.list_deliveries(subscription_id=subscription_id, limit=limit)


@router.post("/webhooks/{subscription_id}/test")
def test_webhook(subscription_id: str, principal: str = Depends(require_operator)):
    """Send a synthetic ping to just this subscription and return the result."""
    sub = webhooks.get_subscription(subscription_id)
    payload = {"ping": True, "event": "person.updated", "at": webhooks.now_iso()}
    return webhooks.deliver(sub, "person.updated", payload, attempt=1)


@router.post("/webhooks/retry")
def retry_webhooks(principal: str = Depends(require_operator)):
    return webhooks.retry_pending()
