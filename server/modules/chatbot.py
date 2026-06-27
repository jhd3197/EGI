"""Channel-agnostic chatbot conversation engine (plan-14 §4/§5).

This is the shared brain behind the WhatsApp and Telegram bots. The thin channel
adapters (``modules/whatsapp_bot.py`` / ``modules/telegram_bot.py``) parse the
provider's webhook payload into a normalized inbound message, call
``handle_message`` here, then send + log the returned reply. Keeping the FSM here
means a new channel is a parser + a sender, not a re-implementation of the flow.

Trust model: every record a conversation creates is a person draft with
``source`` = the channel (``whatsapp``/``telegram``) and ``reviewed = 0`` — both
are in ``moderation.UNTRUSTED_SOURCES``, so a bot report is invisible in public
search until a moderator approves it (plan §3, §14). Search, by contrast, only
ever reads already-trusted records via ``persons.search_persons``.

Conversation state lives in ``chat_sessions`` (one row per channel+user). The
``intent`` (report/safe/search) and ``state`` columns drive a small question
flow so a follow-up answer lands on the right field with minimal typing.

Privacy (plan §14): we never echo or broadcast a shared location; it is attached
only to the current draft. We honor opt-out ("stop"/"detener"): the session is
deleted and no further questions are asked.
"""

import uuid
from typing import Optional

import db
from models import VALID_STATUSES, now_iso
from modules.persons import normalize_cedula, search_persons

# ── Keyword vocabularies (Spanish-first; en/pt accepted) ─────────────────────

OPT_OUT = {
    "stop", "detener", "parar", "salir", "cancelar", "baja", "basta", "no más",
    "no mas", "cancel", "quit",
}

_INTENT_KEYWORDS = {
    "search": {"buscar", "busco", "buscar a alguien", "search", "1"},
    "report": {"reportar", "reporto", "reportar a alguien", "report", "2"},
    "safe": {"estoy bien", "estoybien", "a salvo", "estoy a salvo", "safe", "im ok", "3"},
}

# Free-text → status mapping for the report flow's status question.
_STATUS_KEYWORDS = {
    "missing": {"desaparecido", "desaparecida", "perdido", "perdida", "missing", "1"},
    "found": {"encontrado", "encontrada", "found", "2"},
    "safe": {"a salvo", "salvo", "bien", "safe", "3"},
    "deceased": {"fallecido", "fallecida", "muerto", "muerta", "deceased", "4"},
    "sighted": {"visto", "vista", "avistado", "sighted", "5"},
}

_SKIP = {"no", "-", "n/a", "na", "skip", "omitir", "ninguno", "ninguna", "no sé", "no se"}

# ── Localized bot copy (es default; en/pt fallbacks) ─────────────────────────

_COPY = {
    "es": {
        "welcome": (
            "Hola, soy el asistente de EGI. ¿Qué necesitas?\n"
            "1️⃣ Buscar a alguien\n2️⃣ Reportar a alguien\n3️⃣ Estoy bien"
        ),
        "menu_replies": ["Buscar", "Reportar", "Estoy bien"],
        "ask_query": "Escribe la cédula o el nombre de la persona que buscas.",
        "ask_name": "¿Cuál es el nombre completo de la persona?",
        "ask_name_self": "¿Cuál es tu nombre?",
        "ask_cedula": "¿Cuál es la cédula? (Escribe \"no\" si no la sabes).",
        "ask_location": "¿Dónde se le vio por última vez? Puedes compartir tu ubicación.",
        "ask_status": "¿Cuál es la situación?",
        "status_replies": ["Desaparecido", "Encontrado", "A salvo", "Fallecido", "Visto"],
        "confirm_report": (
            "Recibimos tu reporte sobre {name}. Estado: pendiente de revisión. "
            "Gracias por ayudar."
        ),
        "confirm_safe": (
            "Gracias {name}. Registramos que estás a salvo. "
            "Estado: pendiente de revisión."
        ),
        "search_none": "No encontramos a nadie con esos datos en los registros verificados.",
        "search_header": "Resultados:",
        "search_row": "• {name} — {status}",
        "loc_saved": "Ubicación recibida.",
        "optout": "Conversación finalizada. Escribe cuando quieras para empezar de nuevo.",
        "help": (
            "Comandos: \"buscar\", \"reportar\", \"estoy bien\". "
            "Escribe \"detener\" para terminar."
        ),
        "yes_no_skip": ["No la sé"],
    },
    "en": {
        "welcome": (
            "Hi, I'm the EGI assistant. What do you need?\n"
            "1️⃣ Search for someone\n2️⃣ Report someone\n3️⃣ I'm safe"
        ),
        "menu_replies": ["Search", "Report", "I'm safe"],
        "ask_query": "Type the ID number or the name of the person you're looking for.",
        "ask_name": "What is the person's full name?",
        "ask_name_self": "What is your name?",
        "ask_cedula": "What is the ID number? (Type \"no\" if you don't know it).",
        "ask_location": "Where were they last seen? You can share your location.",
        "ask_status": "What is the situation?",
        "status_replies": ["Missing", "Found", "Safe", "Deceased", "Sighted"],
        "confirm_report": (
            "We received your report about {name}. Status: pending review. "
            "Thank you for helping."
        ),
        "confirm_safe": (
            "Thank you {name}. We recorded that you're safe. Status: pending review."
        ),
        "search_none": "We couldn't find anyone matching that in the verified records.",
        "search_header": "Results:",
        "search_row": "• {name} — {status}",
        "loc_saved": "Location received.",
        "optout": "Conversation ended. Message anytime to start again.",
        "help": "Commands: \"search\", \"report\", \"I'm safe\". Type \"stop\" to end.",
        "yes_no_skip": ["Don't know"],
    },
    "pt": {
        "welcome": (
            "Olá, sou o assistente da EGI. Do que você precisa?\n"
            "1️⃣ Procurar alguém\n2️⃣ Relatar alguém\n3️⃣ Estou bem"
        ),
        "menu_replies": ["Procurar", "Relatar", "Estou bem"],
        "ask_query": "Digite o documento ou o nome da pessoa que procura.",
        "ask_name": "Qual é o nome completo da pessoa?",
        "ask_name_self": "Qual é o seu nome?",
        "ask_cedula": "Qual é o documento? (Escreva \"não\" se não souber).",
        "ask_location": "Onde foi vista pela última vez? Você pode compartilhar sua localização.",
        "ask_status": "Qual é a situação?",
        "status_replies": ["Desaparecido", "Encontrado", "Em segurança", "Falecido", "Avistado"],
        "confirm_report": (
            "Recebemos o seu relato sobre {name}. Estado: pendente de revisão. "
            "Obrigado por ajudar."
        ),
        "confirm_safe": (
            "Obrigado {name}. Registramos que você está em segurança. "
            "Estado: pendente de revisão."
        ),
        "search_none": "Não encontramos ninguém com esses dados nos registros verificados.",
        "search_header": "Resultados:",
        "search_row": "• {name} — {status}",
        "loc_saved": "Localização recebida.",
        "optout": "Conversa encerrada. Envie uma mensagem quando quiser recomeçar.",
        "help": "Comandos: \"procurar\", \"relatar\", \"estou bem\". Escreva \"parar\" para terminar.",
        "yes_no_skip": ["Não sei"],
    },
}


def _t(lang: Optional[str], key: str) -> str:
    lang = lang if lang in _COPY else "es"
    return _COPY[lang].get(key) or _COPY["es"].get(key, key)


def _resp(reply: str, quick_replies=None, session=None, draft=None, ended=False) -> dict:
    return {
        "reply": reply,
        "quick_replies": quick_replies or [],
        "session": session,
        "draft": draft,
        "ended": ended,
    }


# ── Session persistence ──────────────────────────────────────────────────────

def _get_session(channel: str, external_user_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE channel = ? AND external_user_id = ?",
            (channel, external_user_id),
        ).fetchone()
    return db.row_to_dict(row) if row else None


def _create_session(channel: str, external_user_id: str, language: str) -> dict:
    now = now_iso()
    sid = f"chat-{uuid.uuid4().hex[:10]}"
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO chat_sessions "
            "(id, channel, external_user_id, language, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sid, channel, external_user_id, language or "es", now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (sid,)).fetchone()
    return db.row_to_dict(row)


def _update_session(session_id: str, **fields) -> dict:
    fields["updated_at"] = now_iso()
    sets = ", ".join(f"{k} = ?" for k in fields)
    with db.get_db() as conn:
        conn.execute(
            f"UPDATE chat_sessions SET {sets} WHERE id = ?",
            (*fields.values(), session_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    return db.row_to_dict(row)


def _end_session(session_id: str) -> None:
    """Clear the intent/state/draft pointer so the next message starts fresh."""
    _update_session(session_id, intent=None, state=None, current_draft_id=None)


def _delete_session(channel: str, external_user_id: str) -> None:
    with db.get_db() as conn:
        conn.execute(
            "DELETE FROM chat_sessions WHERE channel = ? AND external_user_id = ?",
            (channel, external_user_id),
        )
        conn.commit()


def get_session(session_id: str) -> Optional[dict]:
    """Fetch a session + its current draft (for GET /chatbot/session/{id})."""
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        session = db.row_to_dict(row)
        draft = None
        if session.get("current_draft_id"):
            d = conn.execute(
                "SELECT * FROM persons WHERE id = ?", (session["current_draft_id"],)
            ).fetchone()
            draft = db.row_to_dict(d) if d else None
    return {"session": session, "draft": draft}


# ── Draft persistence ────────────────────────────────────────────────────────

def _mask(external_user_id: str) -> str:
    """Light privacy: keep only the last 4 chars of a phone/account id for audit."""
    s = str(external_user_id or "")
    return ("…" + s[-4:]) if len(s) > 4 else s


def create_draft(channel: str, external_user_id: str, status: str = "missing",
                 disaster_id: Optional[str] = None) -> dict:
    """Create an UNREVIEWED person draft from a chatbot conversation.

    source=<channel>, reviewed=0 → lands in the moderation queue (plan §3).
    """
    if status not in VALID_STATUSES:
        status = "missing"
    now = now_iso()
    pid = f"egi-{channel[:2]}-{uuid.uuid4().hex[:8]}"
    provenance = (
        f"{channel} bot draft from {_mask(external_user_id)} — "
        "UNREVIEWED, verify before trusting"
    )
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO persons
            (id, disaster_id, status, source, provenance, reviewed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (pid, disaster_id, status, channel, provenance, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (pid,)).fetchone()
    return db.row_to_dict(row)


def update_draft(draft_id: str, fields: dict) -> Optional[dict]:
    """Update allowed person columns on a draft; ignores unknown/invalid fields."""
    allowed = {
        "name", "given_name", "family_name", "cedula", "status", "gender", "age",
        "location", "last_known_location", "last_seen_date", "clothes", "notes",
        "contact", "reporter_name", "lat", "lon", "disaster_id",
    }
    clean = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "status" in clean and clean["status"] not in VALID_STATUSES:
        clean.pop("status")
    if not clean:
        return None
    clean["updated_at"] = now_iso()
    sets = ", ".join(f"{k} = ?" for k in clean)
    with db.get_db() as conn:
        cur = conn.execute(
            f"UPDATE persons SET {sets} WHERE id = ?", (*clean.values(), draft_id)
        )
        conn.commit()
        if not cur.rowcount:
            return None
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (draft_id,)).fetchone()
    return db.row_to_dict(row)


# ── Intent / status parsing ──────────────────────────────────────────────────

def _parse_intent(low: str) -> Optional[str]:
    for intent, kws in _INTENT_KEYWORDS.items():
        if low in kws or any(low.startswith(k + " ") for k in kws if len(k) > 2):
            return intent
    return None


def _parse_status(low: str) -> str:
    for status, kws in _STATUS_KEYWORDS.items():
        if low in kws or any(k in low for k in kws if len(k) > 2):
            return status
    return "missing"


def _is_skip(low: str) -> bool:
    return low in _SKIP


# ── Main dispatcher ──────────────────────────────────────────────────────────

def handle_message(
    channel: str,
    external_user_id: str,
    text: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    language: Optional[str] = None,
    disaster_id: Optional[str] = None,
) -> dict:
    """Advance one conversation turn and return the bot's reply + new state.

    Returns ``{reply, quick_replies, session, draft, ended}``. The channel
    adapter is responsible for actually sending ``reply`` and logging messages.
    """
    text = (text or "").strip()
    low = text.lower()

    session = _get_session(channel, external_user_id)
    lang = (session and session.get("language")) or language or "es"

    # Opt-out (plan §14): end the conversation, ask nothing more.
    if low and low in OPT_OUT:
        if session:
            _delete_session(channel, external_user_id)
        return _resp(_t(lang, "optout"), ended=True)

    if low in {"ayuda", "help", "/ayuda", "/help", "ajuda"}:
        return _resp(_t(lang, "help"), session=session)

    if session is None:
        session = _create_session(channel, external_user_id, lang)

    intent = session.get("intent")
    state = session.get("state")
    draft_id = session.get("current_draft_id")

    # A shared location answers the location question (or just gets acked).
    if lat is not None and lon is not None:
        if draft_id:
            update_draft(draft_id, {"lat": lat, "lon": lon,
                                    "last_known_location": f"{lat:.5f}, {lon:.5f}"})
        if intent == "report" and state == "await_location":
            return _ask_status(channel, external_user_id, session, lang)
        if not text:
            return _resp(_t(lang, "loc_saved"), session=session)

    if not intent:
        return _route_intent(channel, external_user_id, session, low, lang, disaster_id)

    if intent == "search":
        return _handle_search(channel, external_user_id, session, text, lang)
    if intent == "report":
        return _handle_report(channel, external_user_id, session, text, low, lat, lon, lang)
    if intent == "safe":
        return _handle_safe(channel, external_user_id, session, text, low, lang)

    # Unknown intent → reset to menu.
    _end_session(session["id"])
    return _welcome(lang, session)


def _welcome(lang: str, session: dict) -> dict:
    return _resp(_t(lang, "welcome"), quick_replies=_COPY.get(lang, _COPY["es"])["menu_replies"],
                 session=session)


def _route_intent(channel, external_user_id, session, low, lang, disaster_id) -> dict:
    parsed = _parse_intent(low)
    if parsed == "search":
        s = _update_session(session["id"], intent="search", state="await_query")
        return _resp(_t(lang, "ask_query"), session=s)
    if parsed == "report":
        draft = create_draft(channel, external_user_id, status="missing", disaster_id=disaster_id)
        s = _update_session(session["id"], intent="report", state="await_name",
                            current_draft_id=draft["id"])
        return _resp(_t(lang, "ask_name"), session=s, draft=draft)
    if parsed == "safe":
        draft = create_draft(channel, external_user_id, status="safe", disaster_id=disaster_id)
        s = _update_session(session["id"], intent="safe", state="await_name",
                            current_draft_id=draft["id"])
        return _resp(_t(lang, "ask_name_self"), session=s, draft=draft)
    return _welcome(lang, session)


def _ask_status(channel, external_user_id, session, lang) -> dict:
    s = _update_session(session["id"], state="await_status")
    return _resp(_t(lang, "ask_status"),
                 quick_replies=_COPY.get(lang, _COPY["es"])["status_replies"], session=s)


def _handle_report(channel, external_user_id, session, text, low, lat, lon, lang) -> dict:
    state = session.get("state")
    draft_id = session.get("current_draft_id")
    if state == "await_name":
        update_draft(draft_id, {"name": text, "reporter_name": _mask(external_user_id)})
        s = _update_session(session["id"], state="await_cedula")
        return _resp(_t(lang, "ask_cedula"), session=s)
    if state == "await_cedula":
        if not _is_skip(low) and text:
            update_draft(draft_id, {"cedula": text})
        s = _update_session(session["id"], state="await_location")
        return _resp(_t(lang, "ask_location"), session=s)
    if state == "await_location":
        if text and not _is_skip(low):
            update_draft(draft_id, {"last_known_location": text, "location": text})
        return _ask_status(channel, external_user_id, session, lang)
    if state == "await_status":
        status = _parse_status(low)
        draft = update_draft(draft_id, {"status": status}) or _draft(draft_id)
        _end_session(session["id"])
        name = (draft or {}).get("name") or "—"
        return _resp(_t(lang, "confirm_report").format(name=name), draft=draft, ended=True)
    # Defensive fallback.
    _end_session(session["id"])
    return _welcome(lang, session)


def _handle_safe(channel, external_user_id, session, text, low, lang) -> dict:
    state = session.get("state")
    draft_id = session.get("current_draft_id")
    if state == "await_name":
        update_draft(draft_id, {"name": text, "reporter_name": text, "status": "safe"})
        s = _update_session(session["id"], state="await_cedula")
        return _resp(_t(lang, "ask_cedula"), session=s)
    if state == "await_cedula":
        if not _is_skip(low) and text:
            update_draft(draft_id, {"cedula": text})
        draft = _draft(draft_id)
        _end_session(session["id"])
        name = (draft or {}).get("name") or "—"
        return _resp(_t(lang, "confirm_safe").format(name=name), draft=draft, ended=True)
    _end_session(session["id"])
    return _welcome(lang, session)


def _handle_search(channel, external_user_id, session, text, lang) -> dict:
    query = (text or "").strip()
    if not query:
        return _resp(_t(lang, "ask_query"), session=session)
    # Decide cédula vs name: a query that normalizes to mostly digits is a cédula.
    norm = normalize_cedula(query)
    if norm and norm.isdigit() and len(norm) >= 5:
        result = search_persons(cedula=query, limit=5)
    else:
        result = search_persons(q=query, limit=5)
    records = result.get("records", [])
    _end_session(session["id"])
    if not records:
        return _resp(_t(lang, "search_none"), ended=True)
    lines = [_t(lang, "search_header")]
    for r in records[:5]:
        name = r.get("name") or " ".join(
            p for p in (r.get("given_name"), r.get("family_name")) if p
        ) or "—"
        status = r.get("derived_status") or r.get("status") or "—"
        lines.append(_t(lang, "search_row").format(name=name, status=status))
    return _resp("\n".join(lines), ended=True)


def _draft(draft_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (draft_id,)).fetchone()
    return db.row_to_dict(row) if row else None
