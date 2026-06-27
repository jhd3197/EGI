"""Voice-note transcription + persistence (plan-14 §6).

EGI prefers **on-device** transcription: the Android wrapper (or the browser
``Web Speech API``) turns a spoken report into text on the phone and sends only
the text. This module is the **server-side fallback** for voice notes that arrive
through WhatsApp/Telegram, where the audio reaches the server as a file:

  * ``transcribe_audio`` runs a local Whisper backend if one is installed
    (``faster_whisper`` preferred, then ``openai-whisper``). With no backend it
    returns ``None`` — transcription is always optional and never hard-fails the
    bot (same local-first degradation as ``ai.py`` / OCR).
  * ``transcribe_whatsapp_audio`` / ``transcribe_telegram_audio`` download the
    provider's audio then transcribe it. Network paths are best-effort.
  * ``save_transcript`` persists the text + confidence to ``voice_transcripts``.

A transcription is marked AI-generated and its confidence is recorded; the bot
prefixes a low-confidence transcript with the recognized text and asks the user
to confirm (plan §6.2). Voice-derived drafts stay ``reviewed=0`` like every other
bot draft, so a human reviews them before they are treated as fact (plan §14).
"""

import os
import tempfile
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

import db
from models import now_iso

# Below this score a transcript is treated as uncertain ("please confirm").
LOW_CONFIDENCE = 0.6


# ── Persistence ──────────────────────────────────────────────────────────────

def save_transcript(
    transcript: str,
    message_id: Optional[str] = None,
    person_id: Optional[str] = None,
    confidence: Optional[float] = None,
    language: Optional[str] = None,
) -> dict:
    """Persist a voice transcript row and return it."""
    now = now_iso()
    vid = f"voice-{uuid.uuid4().hex[:10]}"
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO voice_transcripts "
            "(id, message_id, person_id, transcript, confidence, language, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (vid, message_id, person_id, transcript, confidence, language, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM voice_transcripts WHERE id = ?", (vid,)).fetchone()
    return db.row_to_dict(row)


def list_transcripts(person_id: str) -> dict:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM voice_transcripts WHERE person_id = ? ORDER BY created_at DESC",
            (person_id,),
        ).fetchall()
    return {"records": [db.row_to_dict(r) for r in rows]}


# ── Transcription backends (local-first) ─────────────────────────────────────

def available() -> bool:
    """Whether any local transcription backend is importable (cheap check)."""
    for mod in ("faster_whisper", "whisper"):
        try:
            __import__(mod)
            return True
        except Exception:
            continue
    return False


def transcribe_audio(path: str, language: Optional[str] = None) -> Optional[dict]:
    """Transcribe an audio file with a local Whisper backend, or return None.

    Returns ``{transcript, confidence, language}``. Never raises.
    """
    model_name = os.environ.get("WHISPER_MODEL", "base")

    # 1) faster-whisper (CTranslate2; gives a per-language probability we can use
    #    as a confidence proxy).
    try:
        from faster_whisper import WhisperModel  # type: ignore

        model = WhisperModel(model_name)
        segments, info = model.transcribe(path, language=language)
        text = " ".join(seg.text for seg in segments).strip()
        if text:
            return {
                "transcript": text,
                "confidence": getattr(info, "language_probability", None),
                "language": getattr(info, "language", language),
            }
    except Exception:
        pass

    # 2) openai-whisper (reference implementation; no simple confidence).
    try:
        import whisper  # type: ignore

        model = whisper.load_model(model_name)
        result = model.transcribe(path, language=language)
        text = (result.get("text") or "").strip()
        if text:
            return {
                "transcript": text,
                "confidence": None,
                "language": result.get("language", language),
            }
    except Exception:
        pass

    return None


def _transcribe_bytes(data: bytes, suffix: str = ".ogg",
                      language: Optional[str] = None) -> Optional[dict]:
    """Write audio bytes to a temp file and transcribe; cleans up after itself."""
    if not data:
        return None
    tmp = Path(tempfile.gettempdir()) / f"egi_voice_{uuid.uuid4().hex[:8]}{suffix}"
    try:
        tmp.write_bytes(data)
        return transcribe_audio(str(tmp), language=language)
    except Exception:
        return None
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


# ── Provider audio download (best-effort network paths) ──────────────────────

def _http_get(url: str, headers: Optional[dict] = None) -> Optional[bytes]:  # pragma: no cover - network
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    except Exception:
        return None


def transcribe_whatsapp_audio(audio: dict, cfg: Optional[dict] = None) -> Optional[dict]:  # pragma: no cover - network
    """Download a WhatsApp voice note and transcribe it. Returns None on any miss.

    Twilio delivers a direct ``MediaUrl``; Meta delivers a media ``id`` that must
    be resolved via the Graph API. Both require credentials, so this degrades to
    None when they (or a transcription backend) are absent.
    """
    if not available():
        return None
    data = None
    url = audio.get("url")
    if url:
        sid = (cfg or {}).get("account_sid") or os.environ.get("TWILIO_ACCOUNT_SID")
        token = (cfg or {}).get("auth_token") or os.environ.get("TWILIO_AUTH_TOKEN")
        headers = {}
        if sid and token:
            import base64

            headers["Authorization"] = "Basic " + base64.b64encode(
                f"{sid}:{token}".encode()
            ).decode()
        data = _http_get(url, headers)
    elif audio.get("id"):
        token = (cfg or {}).get("access_token") or os.environ.get("WHATSAPP_ACCESS_TOKEN")
        if not token:
            return None
        meta = _http_get(
            f"https://graph.facebook.com/v19.0/{audio['id']}",
            {"Authorization": f"Bearer {token}"},
        )
        if not meta:
            return None
        import json

        media_url = (json.loads(meta) or {}).get("url")
        if not media_url:
            return None
        data = _http_get(media_url, {"Authorization": f"Bearer {token}"})
    return _transcribe_bytes(data or b"")


def transcribe_telegram_audio(audio: dict, cfg: Optional[dict] = None) -> Optional[dict]:  # pragma: no cover - network
    """Download a Telegram voice note (getFile → file path) and transcribe it."""
    if not available():
        return None
    file_id = audio.get("id")
    token = (cfg or {}).get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not (file_id and token):
        return None
    import json

    info = _http_get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
    if not info:
        return None
    file_path = ((json.loads(info) or {}).get("result") or {}).get("file_path")
    if not file_path:
        return None
    data = _http_get(f"https://api.telegram.org/file/bot{token}/{file_path}")
    return _transcribe_bytes(data or b"")
