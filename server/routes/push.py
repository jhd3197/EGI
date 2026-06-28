"""Push subscription routes (plan-11): subscribe/unsubscribe + VAPID key.

Subscribing is open (any PWA/Android client registers its own device) but rate
limited. Listing subscriptions is operator-gated. Sending is done via alerts
(routes/alerts.py) — this router only manages device registrations.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import current_user, require_operator
from models import PushSubscribeRequest
from modules import push
from ratelimit import rate_limit

router = APIRouter()


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/push/vapid-public-key")
def get_vapid_public_key():
    """The VAPID public key the PWA needs to subscribe (null if not configured)."""
    return {"key": push.vapid_public_key()}


@router.post("/push/subscribe", dependencies=[Depends(rate_limit)])
def subscribe(req: PushSubscribeRequest, user: Optional[dict] = Depends(current_user)):
    return push.subscribe(req, user_id=user["id"] if user else None)


@router.post("/push/unsubscribe", dependencies=[Depends(rate_limit)])
def unsubscribe(req: UnsubscribeRequest):
    return push.unsubscribe(req.endpoint)


@router.get("/push/subscriptions")
def list_subscriptions(topic: Optional[str] = None, principal: str = Depends(require_operator)):
    return push.list_subscriptions(topic=topic)
