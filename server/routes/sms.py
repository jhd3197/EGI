"""SMS routes (plan-02 check-in + plan-11 two-way / outbound / broadcast).

The webhook accepts both a simple JSON body ``{"body": "...", "sender": "..."}``
and the form-encoded shape an SMS gateway like Twilio posts (``Body`` / ``From``),
so a community can wire whichever gateway they have. It handles check-ins AND
replies (two-way conversation). Outbound + broadcast are operator-gated.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from auth import require_role
from models import BroadcastRequest
from modules import sms
from ratelimit import rate_limit

router = APIRouter()

require_operator = require_role("operator")


class SmsNotifyRequest(BaseModel):
    person_id: str
    template_name: str = "report_received"
    to_address: Optional[str] = None
    variables: Optional[dict] = None
    locale: Optional[str] = None


@router.post("/sms/webhook", dependencies=[Depends(rate_limit)])
async def sms_webhook(request: Request):
    body = ""
    sender = None
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        body = data.get("body") or data.get("Body") or ""
        sender = data.get("sender") or data.get("From")
    else:
        form = await request.form()
        body = form.get("body") or form.get("Body") or ""
        sender = form.get("sender") or form.get("From")
    return sms.receive_sms(body, sender)


@router.post("/sms/notify", dependencies=[Depends(rate_limit)])
def sms_notify(req: SmsNotifyRequest, principal: str = Depends(require_operator)):
    """Send a templated SMS to a person (report_received / status_changed / request_info)."""
    return sms.notify_person(
        req.person_id, req.template_name, to_address=req.to_address,
        extra_vars=req.variables, locale=req.locale, actor=principal,
    )


@router.post("/sms/broadcast", dependencies=[Depends(rate_limit)])
def sms_broadcast(req: BroadcastRequest, principal: str = Depends(require_operator)):
    """Broadcast one SMS to a list of numbers (or an operation's contact numbers)."""
    return sms.broadcast(req, actor=principal)
