"""Printable shelter / community poster (plan-14 §9).

A one-page A4 poster a shelter or community point can print and post on a wall.
Unlike the missing-person flyer (``modules/flyer.py``), this carries NO personal
data — just a big QR code that opens EGI (or starts a WhatsApp conversation),
short pictographic instructions, and the operation's name + contact. Scanning the
QR pre-selects the operation (``?op=<id>``) so a volunteer or affected person
lands straight in the right context (plan §9.2).

Like the flyer, reportlab + qrcode are optional: a missing dependency raises a
clear ``RuntimeError`` the route turns into a 503 rather than crashing the app.
"""

import io
import os
import re
from typing import Optional

LABELS = {
    "es": {
        "title": "¿BUSCAS O REPORTAS A ALGUIEN?",
        "subtitle": "Sistema comunitario de reunificación familiar",
        "scan": "Escanea este código con tu teléfono",
        "step_search": "Buscar a una persona",
        "step_report": "Reportar a un desaparecido",
        "step_safe": "Avisar que estás a salvo",
        "no_phone": "¿Sin teléfono? Pide ayuda a un voluntario.",
        "whatsapp": "O escribe por WhatsApp al:",
        "operation": "Operación",
        "contact": "Contacto",
        "disclaimer": "Datos sensibles — solo para reunificación familiar. No compartir fuera del operativo.",
    },
    "en": {
        "title": "LOOKING FOR OR REPORTING SOMEONE?",
        "subtitle": "Community family-reunification system",
        "scan": "Scan this code with your phone",
        "step_search": "Search for a person",
        "step_report": "Report a missing person",
        "step_safe": "Let people know you're safe",
        "no_phone": "No phone? Ask a volunteer for help.",
        "whatsapp": "Or message us on WhatsApp at:",
        "operation": "Operation",
        "contact": "Contact",
        "disclaimer": "Sensitive data — for family reunification only. Do not share outside the operation.",
    },
    "pt": {
        "title": "PROCURANDO OU RELATANDO ALGUÉM?",
        "subtitle": "Sistema comunitário de reunificação familiar",
        "scan": "Leia este código com o seu telefone",
        "step_search": "Procurar uma pessoa",
        "step_report": "Relatar um desaparecido",
        "step_safe": "Avisar que você está em segurança",
        "no_phone": "Sem telefone? Peça ajuda a um voluntário.",
        "whatsapp": "Ou escreva no WhatsApp para:",
        "operation": "Operação",
        "contact": "Contato",
        "disclaimer": "Dados sensíveis — apenas para reunificação familiar. Não compartilhe fora da operação.",
    },
}

DEFAULT_LANG = "es"


def _labels(lang: str) -> dict:
    return LABELS.get((lang or "").lower(), LABELS[DEFAULT_LANG])


def _qr_target(operation_id: str) -> str:
    """The URL the poster QR opens: the PWA with the operation pre-selected."""
    base = (os.environ.get("PUBLIC_BASE_URL") or "http://localhost:3000").rstrip("/")
    return f"{base}/?op={operation_id}"


def _whatsapp_number() -> Optional[str]:
    """A WhatsApp number to advertise on the poster, if one is configured."""
    raw = os.environ.get("WHATSAPP_PUBLIC_NUMBER") or os.environ.get("TWILIO_WHATSAPP_FROM")
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw)
    return cleaned or None


def build_poster(operation_id: str, lang: str = DEFAULT_LANG) -> bytes:
    """Build a one-page A4 PDF poster for an operation and return the PDF bytes.

    Raises ``HTTPException(404)`` if the operation does not exist and
    ``RuntimeError`` (→ 503) if reportlab/qrcode are unavailable.
    """
    try:
        import qrcode
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except Exception as exc:  # pragma: no cover - exercised only without deps
        raise RuntimeError(
            "PDF poster generation requires the 'reportlab' and 'qrcode' "
            f"packages, which are not available: {exc}"
        )

    from modules.operations import get_operation  # 404 if missing

    operation = get_operation(operation_id)
    L = _labels(lang)
    op_name = operation.get("name") or operation_id
    contact = " · ".join(
        p for p in (operation.get("contact_person"), operation.get("contact_phone"),
                    operation.get("municipality")) if p
    )

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm

    # Title banner.
    banner_h = 30 * mm
    c.setFillColorRGB(0.76, 0.15, 0.18)
    c.rect(0, height - banner_h, width, banner_h, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - banner_h + 13 * mm, "EGI")
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(width / 2, height - banner_h + 5 * mm, L["title"])

    y = height - banner_h - 12 * mm
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, y, L["subtitle"])

    # Big QR code, centered.
    qr_img = qrcode.make(_qr_target(operation_id))
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_size = 95 * mm
    qr_x = (width - qr_size) / 2
    qr_y = y - 16 * mm - qr_size
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, qr_y - 9 * mm, L["scan"])

    # Three pictographic steps (number badge + label).
    steps = [
        ("1", L["step_search"], (0.12, 0.37, 0.59)),
        ("2", L["step_report"], (0.80, 0.20, 0.18)),
        ("3", L["step_safe"], (0.11, 0.48, 0.27)),
    ]
    sy = qr_y - 22 * mm
    for num, label, color in steps:
        c.setFillColorRGB(*color)
        c.circle(margin + 5 * mm, sy + 1.5 * mm, 5 * mm, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(margin + 5 * mm, sy - 0.5 * mm, num)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica", 14)
        c.drawString(margin + 14 * mm, sy - 1 * mm, label)
        sy -= 12 * mm

    # Optional WhatsApp number.
    wa = _whatsapp_number()
    if wa:
        sy -= 4 * mm
        c.setFont("Helvetica", 12)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        c.drawString(margin, sy, L["whatsapp"])
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin + 62 * mm, sy, wa)
        sy -= 10 * mm

    c.setFont("Helvetica-Oblique", 11)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawString(margin, sy, L["no_phone"])

    # Operation + contact footer block.
    fy = margin + 14 * mm
    c.setFillColorRGB(0.95, 0.93, 0.90)
    c.rect(0, 0, width, fy + 4 * mm, stroke=0, fill=1)
    c.setFillColorRGB(0.15, 0.13, 0.11)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, fy, f"{L['operation']}: {op_name}")
    if contact:
        c.setFont("Helvetica", 10)
        c.drawCentredString(width / 2, fy - 6 * mm, f"{L['contact']}: {contact}")
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.drawCentredString(width / 2, 4 * mm, L["disclaimer"])

    c.showPage()
    c.save()
    return buf.getvalue()
