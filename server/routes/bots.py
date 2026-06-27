"""Chatbot routes: WhatsApp + Telegram webhooks and the internal chatbot API
(plan-14 §4, §5, §11).

The two webhooks are public (a provider posts to them) and rate-limited like the
SMS webhook. They accept both JSON and form-encoded bodies so a community can
wire whichever gateway they have (Twilio, Meta Cloud API, or the Telegram Bot
API). The ``/chatbot/*`` endpoints are the internal surface: drive a conversation
turn directly (e.g. from a PWA chat widget or a test) and inspect session state.

Bot drafts are created with ``source`` = the channel and ``reviewed = 0``, so
they wait in the moderation queue before appearing in public search.
"""

from typing import Optional

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from modules import chatbot, whatsapp_bot
from ratelimit import rate_limit

router = APIRouter()


async def _read_payload(request: Request) -> dict:
    """Read a webhook body as a dict from JSON or form-encoded content."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return await request.json()
        except Exception:
            return {}
    form = await request.form()
    return {k: v for k, v in form.items()}


@router.post("/webhooks/whatsapp", dependencies=[Depends(rate_limit)])
async def whatsapp_webhook(request: Request):
    payload = await _read_payload(request)
    return whatsapp_bot.process_inbound(payload)


@router.post("/webhooks/telegram", dependencies=[Depends(rate_limit)])
async def telegram_webhook(request: Request):
    # Lazy import keeps this route working even if the Telegram adapter is absent.
    from modules import telegram_bot

    payload = await _read_payload(request)
    return telegram_bot.process_inbound(payload)


# ── Internal chatbot API ─────────────────────────────────────────────────────

class ChatbotDraftRequest(BaseModel):
    channel: str = "whatsapp"
    external_user_id: str
    text: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    language: Optional[str] = None
    disaster_id: Optional[str] = None


@router.post("/chatbot/draft", dependencies=[Depends(rate_limit)])
def chatbot_draft(req: ChatbotDraftRequest):
    """Advance one conversation turn and create/update the draft for a session.

    Channel-agnostic: the same engine that powers WhatsApp/Telegram, callable
    directly so a PWA chat widget (or a test) can drive a report conversation.
    """
    channel = req.channel if req.channel in ("whatsapp", "telegram") else "whatsapp"
    return chatbot.handle_message(
        channel, req.external_user_id, text=req.text, lat=req.lat, lon=req.lon,
        language=req.language, disaster_id=req.disaster_id,
    )


@router.post("/voice/transcribe", dependencies=[Depends(rate_limit)])
async def voice_transcribe(file: UploadFile = File(...), language: str = None):
    """Server-side voice-note transcription fallback (plan-14 §6.2).

    The PWA/Android prefer on-device transcription; this is the fallback when a
    device can't do it locally. Returns ``{transcript, confidence, language,
    low_confidence}`` or 503 when no local transcription backend is installed.
    """
    from modules import voice

    if not voice.available():
        raise HTTPException(
            status_code=503,
            detail="No transcription backend installed (pip install faster-whisper).",
        )
    suffix = Path(file.filename or "audio.ogg").suffix or ".ogg"
    tmp = Path(tempfile.gettempdir()) / f"egi_upload_{uuid.uuid4().hex[:8]}{suffix}"
    try:
        tmp.write_bytes(await file.read())
        result = voice.transcribe_audio(str(tmp), language=language)
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass
    if not result:
        raise HTTPException(status_code=422, detail="Could not transcribe the audio.")
    conf = result.get("confidence")
    result["low_confidence"] = conf is not None and conf < voice.LOW_CONFIDENCE
    return result


@router.get("/chatbot/session/{session_id}")
def chatbot_session(session_id: str):
    """Retrieve a session's current state + the draft it is assembling."""
    result = chatbot.get_session(session_id)
    if not result:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Session not found")
    return result
