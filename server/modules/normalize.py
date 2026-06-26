"""Free-text report normalization.

Turns a messy free-text report (WhatsApp, paper transcript, voice transcript)
into a structured person draft (+ optional report note). The draft is saved with
``source='ai_draft'`` and ``reviewed=0`` so it lands in the moderation queue and
is never treated as fact until a human approves it (plan §7, §12).
"""

import json
import uuid
from typing import Optional

import db
from models import VALID_STATUSES, now_iso

AI_DRAFT_PROVENANCE = (
    "AI-normalized draft from free text — UNREVIEWED, verify before trusting"
)

# Fields the extractor may fill on the person draft.
_PERSON_FIELDS = [
    "name", "given_name", "family_name", "cedula", "status", "gender", "sex",
    "age", "location", "last_seen_date", "clothes", "notes", "contact",
    "reporter_name", "reporter_relation", "reporter_country",
]


def _extract_fields(raw_text: str) -> Optional[dict]:
    """Run the local-first AI extractor over the raw text. Returns a dict of
    fields or None when no AI provider is available. Isolated as its own function
    so tests can monkeypatch it without touching the network."""
    from ai import BaseExtractor

    extractor = BaseExtractor()
    if not extractor.available():
        return None
    prompt = f"""You are normalizing an emergency report about a person during a
disaster. The text may be Spanish or English and informal. Extract a JSON object
with any of these keys you can determine (use null when unknown):
name, given_name, family_name, cedula, status, gender, age, location,
last_seen_date, clothes, notes, contact, reporter_name, reporter_relation.
status must be one of: missing, found, safe, deceased, sighted, care.

Report text:
---
{raw_text}
---
Reply with JSON only."""
    data = extractor.extract(prompt)
    return data if isinstance(data, dict) else None


def normalize_text(raw_text: str, disaster_id: Optional[str] = None) -> dict:
    """Normalize free text into a saved person draft (+ note). Always succeeds:
    if AI is unavailable, it still creates a draft with the raw text in notes so
    an operator can complete it by hand."""
    fields = _extract_fields(raw_text) or {}

    # Keep only known person fields; drop an invalid status (CHECK constraint).
    person = {k: fields.get(k) for k in _PERSON_FIELDS if fields.get(k) is not None}
    if person.get("status") not in VALID_STATUSES:
        person.pop("status", None)
    # Always retain the original text for the reviewer.
    person.setdefault("notes", raw_text)

    now = now_iso()
    person_id = f"egi-ai-{uuid.uuid4().hex[:8]}"
    person.update({
        "id": person_id,
        "disaster_id": disaster_id,
        "source": "ai_draft",
        "reviewed": 0,
        "provenance": AI_DRAFT_PROVENANCE,
        "ocr_text": raw_text,
        "extracted_json": json.dumps(fields) if fields else None,
        "created_at": now,
        "updated_at": now,
    })

    columns = ", ".join(person.keys())
    placeholders = ", ".join(f":{k}" for k in person.keys())
    with db.get_db() as conn:
        conn.execute(
            f"INSERT INTO persons ({columns}) VALUES ({placeholders})", person
        )
        conn.commit()
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        saved = db.row_to_dict(row)

    return {
        "person": saved,
        "ai_used": bool(fields),
        "message": "Draft created (source='ai_draft', reviewed=0). Review before publishing.",
    }
