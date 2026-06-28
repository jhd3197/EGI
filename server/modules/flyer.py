"""Printable missing-person PDF flyer generation (plan-12 Phase 2).

Builds a one-page A4 flyer for a person record: a localized title banner, the
core identity fields, an optional photo (only when ``ENABLE_PHOTOS`` is on and
the file actually exists on disk), and a QR code encoding the contact so a finder
can reach the reporter from a printed sheet. A privacy disclaimer is always
printed: this is sensitive crisis data and a flyer leaves the system.

reportlab / qrcode are optional dependencies. Like the rest of the server's
local-first add-ons (modules/providers.py push, ocr.py easyocr fallback), a
missing dependency degrades gracefully — here by raising a clear RuntimeError the
route turns into a 503 rather than crashing import of the whole app.
"""

import io
import re
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

import uploads
from modules.persons import get_person
from security import photos_enabled

# Localized flyer strings. Spanish first (the default lang); en/pt for the
# diaspora / cross-border reunification use case (plan-12 interoperability).
LABELS = {
    "es": {
        "title": "PERSONA DESAPARECIDA",
        "name": "Nombre",
        "age": "Edad",
        "sex": "Sexo",
        "status": "Estado",
        "last_seen": "Visto por última vez",
        "location": "Ubicación",
        "contact": "Contacto",
        "scan_to_contact": "Escanee para contactar",
        "no_photo": "SIN FOTO",
        "unknown": "Desconocido",
        "disclaimer": "Información sensible — verifíquela antes de compartir.",
    },
    "en": {
        "title": "MISSING PERSON",
        "name": "Name",
        "age": "Age",
        "sex": "Sex",
        "status": "Status",
        "last_seen": "Last seen",
        "location": "Location",
        "contact": "Contact",
        "scan_to_contact": "Scan to contact",
        "no_photo": "NO PHOTO",
        "unknown": "Unknown",
        "disclaimer": "Sensitive information — verify before sharing.",
    },
    "pt": {
        "title": "PESSOA DESAPARECIDA",
        "name": "Nome",
        "age": "Idade",
        "sex": "Sexo",
        "status": "Estado",
        "last_seen": "Visto pela última vez",
        "location": "Localização",
        "contact": "Contato",
        "scan_to_contact": "Digitalize para contatar",
        "no_photo": "SEM FOTO",
        "unknown": "Desconhecido",
        "disclaimer": "Informação sensível — verifique antes de compartilhar.",
    },
}

DEFAULT_LANG = "es"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _labels(lang: str) -> dict:
    return LABELS.get((lang or "").lower(), LABELS[DEFAULT_LANG])


def _qr_target(contact: Optional[str], person_id: str) -> str:
    """Turn the contact into a scannable URI.

    Phone-like -> ``tel:`` (digits only, keeping a leading ``+``); email-like ->
    ``mailto:``; anything else -> the raw string. With no contact at all we still
    encode something useful: an EGI record reference.
    """
    contact = (contact or "").strip()
    if not contact:
        return f"EGI: {person_id}"
    if _EMAIL_RE.match(contact):
        return f"mailto:{contact}"
    digits = re.sub(r"[^\d+]", "", contact)
    # Treat as a phone number when, after stripping formatting, it is mostly
    # digits (allow a leading +). Otherwise fall back to the raw contact text.
    if len(re.sub(r"\D", "", digits)) >= 6:
        return f"tel:{digits}"
    return contact


def _photo_path(person: dict) -> Optional[Path]:
    """Return an existing on-disk photo path for this person, or None.

    Honors ``ENABLE_PHOTOS``: a crisis photo is never embedded when photos are
    disabled. The upload dir is read from ``main`` at call time so the test
    suite's ``main.UPLOAD_DIR`` monkeypatch is respected (same pattern as the
    photo routes).
    """
    if not photos_enabled():
        return None
    ref = person.get("image_path") or person.get("photo_url")
    if not ref:
        return None

    import main  # late import: honor a monkeypatched UPLOAD_DIR at call time

    # Accept either a bare stored filename or a "/uploads/<name>" URL; only files
    # that resolve under the upload dir are embedded (never arbitrary paths).
    name = str(ref).split("/")[-1]
    candidate = uploads.safe_path(main.UPLOAD_DIR, name)
    if candidate is not None and candidate.is_file():
        return candidate
    return None


def build_flyer(person_id: str, lang: str = DEFAULT_LANG) -> bytes:
    """Build a one-page A4 PDF flyer for a person and return the PDF bytes.

    Raises ``HTTPException(404)`` if the person does not exist and
    ``RuntimeError`` if the PDF/QR dependencies are unavailable (the route maps
    that to a 503).
    """
    try:
        import qrcode
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except Exception as exc:  # pragma: no cover - exercised only without deps
        raise RuntimeError(
            "PDF flyer generation requires the 'reportlab' and 'qrcode' "
            f"packages, which are not available: {exc}"
        )

    person = get_person(person_id)  # 404 if missing
    L = _labels(lang)

    def _val(*keys: str) -> Optional[str]:
        for k in keys:
            v = person.get(k)
            if v not in (None, ""):
                return v
        return None

    name = (
        _val("name")
        or " ".join(
            p for p in (person.get("given_name"), person.get("family_name")) if p
        )
        or L["unknown"]
    )
    age = _val("age")
    sex = _val("sex", "gender")
    status = _val("derived_status", "status")
    last_seen = _val("last_seen_date")
    location = _val("last_known_location", "location")
    contact = _val("contact")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm

    # Title banner.
    banner_h = 22 * mm
    c.setFillColorRGB(0.72, 0.10, 0.10)
    c.rect(0, height - banner_h, width, banner_h, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - banner_h + 7 * mm, L["title"])

    # Layout: photo/placeholder box on the left, QR on the right.
    top = height - banner_h - 12 * mm
    box_w = 55 * mm
    box_h = 55 * mm
    box_x = margin
    box_y = top - box_h

    photo_path = _photo_path(person)
    if photo_path is not None:
        try:
            c.drawImage(
                ImageReader(str(photo_path)),
                box_x, box_y, width=box_w, height=box_h,
                preserveAspectRatio=True, anchor="c", mask="auto",
            )
        except Exception:
            photo_path = None  # fall through to placeholder on any decode error
    if photo_path is None:
        c.setFillColorRGB(0.93, 0.93, 0.93)
        c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=1)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(box_x + box_w / 2, box_y + box_h / 2, L["no_photo"])

    # QR code (top right).
    qr_img = qrcode.make(_qr_target(contact, person_id))
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_size = 40 * mm
    qr_x = width - margin - qr_size
    qr_y = top - qr_size
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica", 8)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 4 * mm, L["scan_to_contact"])

    # Name headline below the boxes.
    y = box_y - 14 * mm
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, y, str(name))

    # Detail rows.
    rows = [
        (L["age"], age),
        (L["sex"], sex),
        (L["status"], status),
        (L["last_seen"], last_seen),
        (L["location"], location),
        (L["contact"], contact),
    ]
    y -= 12 * mm
    for label, value in rows:
        if value in (None, ""):
            continue
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, f"{label}:")
        c.setFont("Helvetica", 12)
        c.drawString(margin + 42 * mm, y, str(value))
        y -= 9 * mm

    # Privacy disclaimer footer.
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, margin, L["disclaimer"])

    c.showPage()
    c.save()
    return buf.getvalue()
