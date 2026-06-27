"""Telegram channel adapter for the chatbot engine (plan-14 §5).

A thin adapter over the same ``modules/chatbot.py`` FSM that powers WhatsApp —
Telegram is "Phase 2, parallel, low-cost": its Bot API is a single HTTPS call and
is widely used by diaspora communities and aid groups. We add only what differs:

  * the Telegram *update* JSON shape (``message.chat.id`` is the reply address),
  * slash *commands* (``/buscar``, ``/reportar``, ``/estoybien``, ``/ayuda``)
    mapped onto the channel-agnostic intents.

Drafts are ``source='telegram'``, ``reviewed=0`` → moderation queue, same as
WhatsApp. Replies + inbound are logged via ``modules/messaging.py``.
"""

from typing import Optional

from modules import chatbot, messaging, providers

CHANNEL = "telegram"

# Slash command → the plain text the engine understands. ``/buscar`` may carry an
# inline query (``/buscar V-123``) which we forward as a second turn.
_COMMANDS = {
    "/reportar": "reportar",
    "/report": "reportar",
    "/estoybien": "estoy bien",
    "/safe": "estoy bien",
    "/ayuda": "ayuda",
    "/help": "ayuda",
    "/start": "hola",
    "/buscar": "buscar",
    "/search": "buscar",
}


def parse_inbound(payload: dict) -> Optional[dict]:
    """Normalize a Telegram update into ``{external_user_id, text, lat, lon, media}``.

    Returns ``None`` for updates without a usable message (edited messages,
    callbacks, etc. are ignored so the webhook still acks them).
    """
    if not isinstance(payload, dict):
        return None
    msg = payload.get("message") or payload.get("edited_message")
    if not msg:
        return None
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return None
    text = msg.get("text") or msg.get("caption")
    lat = lon = None
    media = []
    if msg.get("location"):
        lat = msg["location"].get("latitude")
        lon = msg["location"].get("longitude")
    if msg.get("voice"):
        media.append({"kind": "audio", "id": msg["voice"].get("file_id")})
    elif msg.get("audio"):
        media.append({"kind": "audio", "id": msg["audio"].get("file_id")})
    elif msg.get("photo"):
        # Telegram sends multiple sizes; the last is the largest.
        photos = msg["photo"]
        media.append({"kind": "image", "id": photos[-1].get("file_id") if photos else None})
    return {"external_user_id": str(chat_id), "text": text, "lat": lat, "lon": lon,
            "media": media}


def _expand_command(text: Optional[str]) -> list:
    """Turn a slash command into the 1-2 plain-text turns the engine expects."""
    if not text:
        return [text]
    stripped = text.strip()
    if not stripped.startswith("/"):
        return [text]
    parts = stripped.split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]  # strip optional @botname suffix
    arg = parts[1] if len(parts) > 1 else None
    base = _COMMANDS.get(cmd)
    if base is None:
        return [text]
    if cmd in ("/buscar", "/search") and arg:
        return ["buscar", arg]  # enter search, then forward the query
    return [base]


def _maybe_transcribe(inbound: dict, cfg: Optional[dict]) -> Optional[dict]:
    media = inbound.get("media") or []
    audio = next((m for m in media if m.get("kind") == "audio"), None)
    if not audio:
        return None
    try:
        from modules import voice
    except Exception:
        return None
    return voice.transcribe_telegram_audio(audio, cfg=cfg)


def process_inbound(payload: dict, disaster_id: Optional[str] = None) -> dict:
    """Handle one Telegram update end to end and return a summary."""
    inbound = parse_inbound(payload)
    if not inbound or not inbound.get("external_user_id"):
        return {"ok": True, "ignored": True}

    chat_id = inbound["external_user_id"]
    cfg = messaging.get_provider_config(CHANNEL)
    text = inbound.get("text")

    transcript = _maybe_transcribe(inbound, cfg)
    if transcript and transcript.get("transcript"):
        text = transcript["transcript"]

    inbound_msg = messaging.record_message(
        channel=CHANNEL, direction="inbound", from_address=chat_id,
        body=(text or "")[:1000], status="delivered",
    )
    if transcript:
        from modules import voice
        voice.save_transcript(
            transcript["transcript"], message_id=inbound_msg["id"],
            confidence=transcript.get("confidence"), language=transcript.get("language"),
        )

    # An explicit action command starts fresh: drop any in-progress intent so a
    # mid-conversation /reportar isn't consumed as the previous question's answer
    # (/ayuda and /help are informational and must NOT reset the flow).
    if text and text.strip().split()[0].lower().split("@")[0] in _COMMANDS \
            and _COMMANDS[text.strip().split()[0].lower().split("@")[0]] != "ayuda":
        chatbot.reset(CHANNEL, chat_id)

    # A slash command may expand into two engine turns (e.g. /buscar V-123).
    turns = _expand_command(text)
    result = {"reply": "", "quick_replies": [], "draft": None, "ended": False}
    for turn in turns:
        result = chatbot.handle_message(
            CHANNEL, chat_id, text=turn,
            lat=inbound.get("lat"), lon=inbound.get("lon"), disaster_id=disaster_id,
        )

    reply = result.get("reply") or ""
    if transcript and (transcript.get("confidence") or 1.0) < 0.6:
        reply = "🎙️ \"" + transcript["transcript"][:120] + "\"\n" + reply

    send_result = providers.send_telegram(chat_id, reply, cfg) if reply else {"status": "skipped"}
    out_msg = messaging.record_message(
        channel=CHANNEL, direction="outbound", to_address=chat_id, body=reply,
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
