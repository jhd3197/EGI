"""Situation Report (SITREP) generation for an operation (plan-13 §3 Reports).

Pulls together the dashboard aggregates (status counts, intake time series,
active tasks, data-quality summary, suggested search sectors) into a single
operation summary that can be rendered as JSON, a self-contained HTML page, or a
one-page PDF.

Spanish-first (the crisis context), like the rest of the user-facing surface.
HTML and JSON always work; the PDF path depends on reportlab and degrades to a
clear RuntimeError (the route maps it to 503) exactly like ``modules/flyer.py``.
"""

import html
import io
from typing import Optional

from fastapi import HTTPException

from models import now_iso
from modules import geo, quality, stats

VALID_FORMATS = {"json", "html", "pdf"}

_STATUS_ES = {
    "missing": "Desaparecido",
    "found": "Encontrado",
    "safe": "A salvo",
    "deceased": "Fallecido",
    "sighted": "Avistado",
    "care": "Bajo cuidado",
    "unknown": "Desconocido",
}


def build_report_data(op_id: str) -> dict:
    """Assemble the structured SITREP payload for an operation (404 if absent)."""
    op = stats.operation_stats(op_id)  # raises 404 if the operation is unknown
    timeseries = stats.operation_timeseries(op_id, days=14)
    try:
        sectors = geo.suggested_sectors(op_id, top=5)
    except HTTPException:
        sectors = {"sectors": [], "count": 0}
    return {
        "generated_at": now_iso(),
        "operation": {
            "id": op_id,
            "name": op.get("name"),
            "status": op.get("status"),
        },
        "metrics": {
            "persons_total": op["persons_total"],
            "persons_by_status": op["persons_by_status"],
            "geolocated_persons": op["geolocated_persons"],
            "pending_review": op["pending_review"],
            "tasks": op["tasks"],
        },
        "recent_intake": timeseries["new_reports"][:14],
        "resolved": timeseries["resolved"][:14],
        "quality": quality.summary(),
        "suggested_sectors": sectors["sectors"],
    }


def _fmt_status_rows(by_status: dict) -> list:
    return [(_STATUS_ES.get(k, k), v) for k, v in by_status.items() if v]


def render_html(data: dict) -> str:
    """Render the SITREP as a standalone, printable HTML document (Spanish)."""
    op = data["operation"]
    m = data["metrics"]
    q = data["quality"]

    def esc(v):
        return html.escape(str(v if v is not None else "—"))

    status_rows = "".join(
        f"<tr><td>{esc(label)}</td><td class='num'>{esc(n)}</td></tr>"
        for label, n in _fmt_status_rows(m["persons_by_status"])
    ) or "<tr><td colspan='2'>Sin registros</td></tr>"

    intake_rows = "".join(
        f"<tr><td>{esc(d['day'])}</td><td class='num'>{esc(d['count'])}</td></tr>"
        for d in data["recent_intake"]
    ) or "<tr><td colspan='2'>—</td></tr>"

    sector_rows = "".join(
        f"<tr><td>{esc(s['sector'])}</td>"
        f"<td class='num'>{esc(s['weight'])}</td>"
        f"<td>{esc(round(s['centroid']['lat'], 5))}, {esc(round(s['centroid']['lon'], 5))}</td></tr>"
        for s in data["suggested_sectors"]
    ) or "<tr><td colspan='3'>Sin zonas calientes</td></tr>"

    issues = q.get("issues") or {}
    issue_rows = "".join(
        f"<tr><td>{esc(k)}</td><td class='num'>{esc(v)}</td></tr>"
        for k, v in sorted(issues.items())
    ) or "<tr><td colspan='2'>—</td></tr>"

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>SITREP — {esc(op.get('name') or op['id'])}</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; margin: 32px; }}
  h1 {{ color: #b71c1c; margin-bottom: 0; }}
  .meta {{ color: #555; font-size: 13px; margin-bottom: 24px; }}
  h2 {{ border-bottom: 2px solid #b71c1c; padding-bottom: 4px; margin-top: 28px; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 540px; margin-top: 8px; }}
  td, th {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .card {{ background: #f5f5f5; border-radius: 8px; padding: 12px 18px; min-width: 120px; }}
  .card .v {{ font-size: 28px; font-weight: bold; }}
  .card .l {{ font-size: 12px; color: #666; }}
  footer {{ margin-top: 32px; color: #888; font-size: 11px; }}
</style></head><body>
<h1>SITREP — {esc(op.get('name') or op['id'])}</h1>
<div class="meta">Estado de la operación: <b>{esc(op.get('status'))}</b> ·
  Generado: {esc(data['generated_at'])}</div>

<div class="cards">
  <div class="card"><div class="v">{esc(m['persons_total'])}</div><div class="l">Personas</div></div>
  <div class="card"><div class="v">{esc(m['tasks']['active'])}</div><div class="l">Tareas activas</div></div>
  <div class="card"><div class="v">{esc(m['pending_review'])}</div><div class="l">Pendientes de revisión</div></div>
  <div class="card"><div class="v">{esc(m['geolocated_persons'])}</div><div class="l">Geolocalizadas</div></div>
</div>

<h2>Personas por estado</h2>
<table><tr><th>Estado</th><th class="num">Total</th></tr>{status_rows}</table>

<h2>Ingresos recientes (por día)</h2>
<table><tr><th>Día</th><th class="num">Nuevos</th></tr>{intake_rows}</table>

<h2>Zonas de búsqueda sugeridas</h2>
<table><tr><th>Sector</th><th class="num">Densidad</th><th>Centro (lat, lon)</th></tr>{sector_rows}</table>

<h2>Calidad de datos</h2>
<p>Puntaje promedio: <b>{esc(q.get('avg_score'))}</b> ·
   Registros evaluados: {esc(q.get('scored'))}</p>
<table><tr><th>Problema</th><th class="num">Conteo</th></tr>{issue_rows}</table>

<footer>EGI · Información sensible — verifíquela antes de compartir.</footer>
</body></html>"""


def render_pdf(data: dict) -> bytes:
    """Render the SITREP as a one-page A4 PDF. Raises RuntimeError without reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception as exc:  # pragma: no cover - exercised only without deps
        raise RuntimeError(
            "SITREP PDF generation requires the 'reportlab' package, which is "
            f"not available: {exc}"
        )

    op = data["operation"]
    m = data["metrics"]
    q = data["quality"]

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm

    banner_h = 18 * mm
    c.setFillColorRGB(0.72, 0.10, 0.10)
    c.rect(0, height - banner_h, width, banner_h, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 20)
    title = f"SITREP — {op.get('name') or op['id']}"
    c.drawString(margin, height - banner_h + 5 * mm, title[:60])

    y = height - banner_h - 10 * mm
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, f"Estado: {op.get('status')}  ·  Generado: {data['generated_at']}")

    def section(label):
        nonlocal y
        y -= 9 * mm
        c.setFillColorRGB(0.72, 0.10, 0.10)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, y, label)
        c.setFillColorRGB(0, 0, 0)
        y -= 6 * mm

    def line(text):
        nonlocal y
        c.setFont("Helvetica", 11)
        c.drawString(margin + 4 * mm, y, text[:90])
        y -= 6 * mm

    section("Métricas clave")
    line(f"Personas: {m['persons_total']}   Tareas activas: {m['tasks']['active']}/{m['tasks']['total']}")
    line(f"Pendientes de revisión: {m['pending_review']}   Geolocalizadas: {m['geolocated_persons']}")

    section("Personas por estado")
    for label, n in _fmt_status_rows(m["persons_by_status"]):
        line(f"{label}: {n}")
    if not any(m["persons_by_status"].values()):
        line("Sin registros")

    section("Zonas de búsqueda sugeridas")
    if data["suggested_sectors"]:
        for s in data["suggested_sectors"]:
            cen = s["centroid"]
            line(f"{s['sector']}: densidad {s['weight']} @ {round(cen['lat'], 5)}, {round(cen['lon'], 5)}")
    else:
        line("Sin zonas calientes")

    section("Calidad de datos")
    line(f"Puntaje promedio: {q.get('avg_score')}   Evaluados: {q.get('scored')}")

    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, margin, "EGI · Información sensible — verifíquela antes de compartir.")

    c.showPage()
    c.save()
    return buf.getvalue()


def generate(op_id: str, fmt: str = "json"):
    """Generate a SITREP in the requested format.

    Returns a dict (json), str (html) or bytes (pdf). Raises 400 on a bad format,
    404 on an unknown operation, and RuntimeError (→503) if a PDF is requested
    without reportlab.
    """
    fmt = (fmt or "json").lower()
    if fmt not in VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {sorted(VALID_FORMATS)}")
    data = build_report_data(op_id)
    if fmt == "json":
        return data
    if fmt == "html":
        return render_html(data)
    return render_pdf(data)
