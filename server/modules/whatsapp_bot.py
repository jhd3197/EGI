"""WhatsApp channel adapter for the chatbot engine (plan-14 §4).

Thin glue between a WhatsApp provider webhook and ``modules/chatbot.py``:

  1. ``parse_inbound`` normalizes the two payload shapes EGI supports — Twilio's
     form-encoded webhook and the Meta WhatsApp Cloud API JSON — into one
     ``{external_user_id, text, lat, lon, media}`` dict.
  2. ``process_inbound`` records the inbound message, runs the conversation turn,
     downloads + transcribes any voice note (best-effort), sends the reply via
     ``providers.send_whatsapp`` and records the outbound message.

Everything funnels through ``modules/messaging.py`` so a commander sees the bot
conversation in the same unified message log as SMS/email (plan §4.4: "Replies
are logged in the messages table").
"""

from typing import Optional

import normalize
from modules import chatbot, messaging, providers

CHANNEL = "whatsapp"


def _digits(value: Optional[str]) -> str:
    """Reduce a WhatsApp address (``whatsapp:+58…``) to a clean phone string."""
    return normalize.normalize_phone(value, "whatsapp")


def parse_inbound(payload: dict) -> Optional[dict]:
    """Normalize a Twilio-or-Meta WhatsApp webhook into one inbound dict.

    Returns ``None`` for payloads with no user message (e.g. a pure delivery
    status callback), so the route can ack them without replying.
    """
    if not isinstance(payload, dict):
        return None

    # ── Meta WhatsApp Cloud API shape ────────────────────────────────────────
    if "entry" in payload:
        try:
            value = payload["entry"][0]["changes"][0]["value"]
        except (KeyError, IndexError, TypeError):
            return None
        messages = value.get("messages") or []
        if not messages:
            return None  # status callback, not a user message
        msg = messages[0]
        sender = _digits(msg.get("from"))
        mtype = msg.get("type")
        text = None
        lat = lon = None
        media = []
        if mtype == "text":
            text = (msg.get("text") or {}).get("body")
        elif mtype == "location":
            loc = msg.get("location") or {}
            lat, lon = loc.get("latitude"), loc.get("longitude")
        elif mtype in ("audio", "voice"):
            media.append({"kind": "audio", "id": (msg.get(mtype) or {}).get("id")})
        elif mtype == "image":
            media.append({"kind": "image", "id": (msg.get("image") or {}).get("id")})
        return {"external_user_id": sender, "text": text, "lat": lat, "lon": lon,
                "media": media, "provider": "meta"}

    # ── Twilio form-encoded shape ────────────────────────────────────────────
    sender = _digits(payload.get("From") or payload.get("from"))
    if not sender:
        return None
    text = payload.get("Body") or payload.get("body")
    lat = payload.get("Latitude")
    lon = payload.get("Longitude")
    media = []
    try:
        num_media = int(payload.get("NumMedia") or 0)
    except (TypeError, ValueError):
        num_media = 0
    for i in range(num_media):
        url = payload.get(f"MediaUrl{i}")
        ctype = payload.get(f"MediaContentType{i}") or ""
        kind = "audio" if ctype.startswith("audio") else (
            "image" if ctype.startswith("image") else "file")
        media.append({"kind": kind, "url": url, "content_type": ctype})
    return {
        "external_user_id": sender,
        "text": text,
        "lat": float(lat) if lat not in (None, "") else None,
        "lon": float(lon) if lon not in (None, "") else None,
        "media": media,
        "provider": "twilio",
    }


def _maybe_transcribe(inbound: dict, cfg: Optional[dict]) -> Optional[dict]:
    """Best-effort voice-note transcription (plan-14 §6). Returns a transcript
    dict {transcript, confidence, language} or None. Never raises."""
    media = inbound.get("media") or []
    audio = next((m for m in media if m.get("kind") == "audio"), None)
    if not audio:
        return None
    try:
        from modules import voice
    except Exception:
        return None
    return voice.transcribe_whatsapp_audio(audio, cfg=cfg)


def process_inbound(payload: dict, disaster_id: Optional[str] = None) -> dict:
    """Handle one inbound WhatsApp webhook end to end and return a summary."""
    inbound = parse_inbound(payload)
    if not inbound or not inbound.get("external_user_id"):
        return {"ok": True, "ignored": True}

    sender = inbound["external_user_id"]
    cfg = messaging.get_provider_config(CHANNEL)
    text = inbound.get("text")

    # Voice note → transcript becomes the message text (low confidence is flagged).
    transcript = _maybe_transcribe(inbound, cfg)
    if transcript and transcript.get("transcript"):
        text = transcript["transcript"]

    inbound_msg = messaging.record_message(
        channel=CHANNEL, direction="inbound", from_address=sender,
        body=(text or "")[:1000], status="delivered",
    )
    if transcript:
        from modules import voice
        voice.save_transcript(
            transcript["transcript"], message_id=inbound_msg["id"],
            confidence=transcript.get("confidence"), language=transcript.get("language"),
        )

    result = chatbot.handle_message(
        CHANNEL, sender, text=text,
        lat=inbound.get("lat"), lon=inbound.get("lon"), disaster_id=disaster_id,
    )

    reply = result.get("reply") or ""
    # A low-confidence voice transcript: ask the user to confirm (plan §6.2).
    if transcript and (transcript.get("confidence") or 1.0) < 0.6:
        reply = "🎙️ \"" + transcript["transcript"][:120] + "\"\n" + reply

    send_result = providers.send_whatsapp(sender, reply, cfg) if reply else {"status": "skipped"}
    out_msg = messaging.record_message(
        channel=CHANNEL, direction="outbound", to_address=sender, body=reply,
        status=send_result.get("status", "pending"), error=send_result.get("error"),
        external_id=send_result.get("external_id"),
        person_id=(result.get("draft") or {}).get("id"),
    )
    return {
        "ok": True,
        "reply": reply,
        "quick_replies": result.get("quick_replies", []),
        "draft": result.get("draft"),
        "inbound_message_id": inbound_msg["id"],
        "outbound_message_id": out_msg["id"],
        "ended": result.get("ended", False),
    }
