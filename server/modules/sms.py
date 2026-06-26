"""SMS fallback: a text-only emergency check-in (layer-1 fallback path).

A community member with no data/internet texts a structured message to a
configured number; a gateway (Twilio, a local GSM modem, or a community provider)
forwards it to ``POST /sms/webhook``. We parse it into a ``safe`` self check-in
and store it as an UNTRUSTED record (source='sms', reviewed=0) so a moderator
must approve it before it shows in public search.

Format (case-insensitive keyword, comma- or space-separated fields):
    EGI CHECKIN <cedula> <name> <location>
    EGI CHECKIN V-12345678, Juan Pérez, Refugio Norte

Privacy: text-only. No photos or exact coordinates (see plan §14).
"""

import re
import uuid
from typing import Optional

from fastapi import HTTPException

import db
from models import now_iso

KEYWORD = "EGI CHECKIN"


def parse_checkin(body: str) -> dict:
    """Parse an EGI CHECKIN message into {cedula, name, location}.

    Raises HTTPException(400) when the keyword is missing or no cédula is found.
    """
    if not body:
        raise HTTPException(status_code=400, detail="empty SMS body")
    text = body.strip()
    upper = text.upper()
    if not upper.startswith(KEYWORD):
        raise HTTPException(status_code=400, detail="not an EGI CHECKIN message")

    remainder = text[len(KEYWORD):].strip()
    if not remainder:
        raise HTTPException(status_code=400, detail="missing check-in fields")

    if "," in remainder:
        parts = [p.strip() for p in remainder.split(",")]
        cedula = parts[0] if len(parts) > 0 else ""
        name = parts[1] if len(parts) > 1 else ""
        location = parts[2] if len(parts) > 2 else ""
    else:
        # Whitespace form: first token is the cédula, last token the location,
        # everything between is the name (best effort).
        tokens = remainder.split()
        cedula = tokens[0] if tokens else ""
        if len(tokens) >= 3:
            name = " ".join(tokens[1:-1])
            location = tokens[-1]
        elif len(tokens) == 2:
            name, location = tokens[1], ""
        else:
            name, location = "", ""

    if not cedula:
        raise HTTPException(status_code=400, detail="missing cédula in check-in")
    return {"cedula": cedula, "name": name, "location": location}


def receive_checkin(body: str, sender: Optional[str] = None) -> dict:
    """Create a ``safe`` self check-in person record from an SMS body.

    Stored as source='sms', reviewed=0 (untrusted → moderator-only until approved).
    """
    fields = parse_checkin(body)
    now = now_iso()
    person_id = f"egi-sms-{uuid.uuid4().hex[:8]}"
    name = fields["name"] or "Check-in SMS"
    location = fields["location"]
    # Provenance keeps the raw text + sender (digits only, light privacy) for audit.
    safe_sender = re.sub(r"[^0-9+]", "", sender) if sender else None
    provenance = f"SMS check-in from {safe_sender or 'unknown'}: {body.strip()[:160]}"

    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO persons
            (id, name, status, location, last_known_location, cedula, source,
             provenance, reviewed, reporter_name, created_at, updated_at)
            VALUES (?, ?, 'safe', ?, ?, ?, 'sms', ?, 0, ?, ?, ?)
            """,
            (person_id, name, location, location, fields["cedula"], provenance,
             name, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    return {"created": db.row_to_dict(row), "parsed": fields}
