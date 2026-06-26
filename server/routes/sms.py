"""Route for the SMS check-in webhook.

Accepts both a simple JSON body ``{"body": "...", "sender": "..."}`` and the
form-encoded shape an SMS gateway like Twilio posts (``Body`` / ``From``), so a
community can wire whichever gateway they have.
"""

from fastapi import APIRouter, Request

from modules import sms

router = APIRouter()


@router.post("/sms/webhook")
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
    return sms.receive_checkin(body, sender)
