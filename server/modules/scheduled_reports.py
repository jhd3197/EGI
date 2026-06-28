"""Scheduled SITREP reports (plan-13 §3 Reports).

An operator registers a recurring report against an operation: a format
(``html``/``json``/``pdf``), a coarse schedule, and a recipient list (emails
and/or webhook subscription ids). The runner (``run_due`` — driven by the
``egi run-reports`` CLI or cron) finds reports whose schedule is due, generates
the SITREP, delivers it to each recipient, and stamps ``last_run_at``.

Delivery degrades gracefully like the rest of the comms hub: email goes through
``modules.messaging`` (falls back to the ``log`` driver with no SMTP creds) and
webhooks through ``modules.webhooks`` (urllib). A PDF schedule with reportlab
absent records a failure for that run but never raises.

Schedule is intentionally simple — a keyword interval the runner can evaluate
without a cron parser:
  * ``hourly``  — due if last run was > 1 hour ago (or never).
  * ``daily``   — due if last run was > 24 hours ago (or never).
  * ``weekly``  — due if last run was > 7 days ago (or never).
A raw cron-like string is stored verbatim and treated as ``daily`` for the
due-check (documented limitation; the field is preserved for a future parser).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

import db
import timeutil
from models import now_iso

VALID_FORMATS = {"pdf", "html", "json"}

# Keyword interval -> minimum elapsed time before a report is "due" again.
_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}
_DEFAULT_INTERVAL = timedelta(days=1)


def _row_to_dict(row) -> dict:
    return db.row_to_dict(row)


def create_report(operation_id: Optional[str], name: Optional[str], fmt: str,
                  schedule_cron: str, recipients: str,
                  actor: str = "system") -> dict:
    fmt = (fmt or "html").lower()
    if fmt not in VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {sorted(VALID_FORMATS)}")
    if not (recipients or "").strip():
        raise HTTPException(status_code=400, detail="recipients is required")
    # Validate the operation exists if one is targeted (None = global SITREP).
    if operation_id:
        with db.get_db() as conn:
            if not conn.execute("SELECT id FROM events WHERE id = ?", (operation_id,)).fetchone():
                raise HTTPException(status_code=404, detail="Operation not found")
    now = now_iso()
    rid = f"report-{uuid.uuid4().hex[:8]}"
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO scheduled_reports "
            "(id, operation_id, name, format, schedule_cron, recipients, "
            " last_run_at, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, 1, ?)",
            (rid, operation_id, name, fmt, schedule_cron or "daily", recipients, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM scheduled_reports WHERE id = ?", (rid,)).fetchone()
    from modules import audit
    audit.log_action(actor, "scheduled_report_create", "scheduled_report", rid,
                     detail=f"format={fmt} schedule={schedule_cron}")
    return _row_to_dict(row)


def list_reports(active_only: bool = False) -> dict:
    sql = "SELECT * FROM scheduled_reports"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql).fetchall()
    return {"reports": [_row_to_dict(r) for r in rows]}


def get_report(report_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM scheduled_reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    return _row_to_dict(row)


def delete_report(report_id: str, actor: str = "system") -> dict:
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM scheduled_reports WHERE id = ?", (report_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Scheduled report not found")
        conn.commit()
    from modules import audit
    audit.log_action(actor, "scheduled_report_delete", "scheduled_report", report_id)
    return {"ok": True, "id": report_id}


def set_active(report_id: str, active: bool, actor: str = "system") -> dict:
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE scheduled_reports SET active = ? WHERE id = ?",
            (1 if active else 0, report_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Scheduled report not found")
        conn.commit()
        row = conn.execute("SELECT * FROM scheduled_reports WHERE id = ?", (report_id,)).fetchone()
    return _row_to_dict(row)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO-8601 to a tz-aware UTC datetime — delegates to ``timeutil.parse_iso``."""
    dt = timeutil.parse_iso(value)
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _interval_for(schedule_cron: Optional[str]) -> timedelta:
    return _INTERVALS.get((schedule_cron or "").strip().lower(), _DEFAULT_INTERVAL)


def is_due(report: dict, now: Optional[datetime] = None) -> bool:
    """True if the report is active and enough time has elapsed since last run."""
    if not report.get("active"):
        return False
    now = now or datetime.now(timezone.utc)
    last = _parse_dt(report.get("last_run_at"))
    if last is None:
        return True
    return (now - last) >= _interval_for(report.get("schedule_cron"))


def _deliver(report: dict, data: dict, html_body: str) -> dict:
    """Deliver a generated SITREP to each recipient (email or webhook id)."""
    from modules import messaging, webhooks
    from models import SendMessageRequest

    sent, failed = 0, 0
    op_name = (data.get("operation") or {}).get("name") or report.get("operation_id") or "global"
    subject = f"SITREP — {op_name}"
    recipients = [r.strip() for r in (report.get("recipients") or "").split(",") if r.strip()]
    for recipient in recipients:
        try:
            if "@" in recipient:
                req = SendMessageRequest(
                    channel="email", to_address=recipient, subject=subject,
                    body=html_body, operation_id=report.get("operation_id"),
                )
                messaging.send_message(req, actor="scheduled_report")
            else:
                # Treat as a webhook subscription id: deliver the JSON payload.
                sub = webhooks.get_subscription(recipient)
                webhooks.deliver(
                    sub, "report.sitrep",
                    {"report_id": report["id"], "sitrep": data},
                )
            sent += 1
        except Exception:
            failed += 1
    return {"sent": sent, "failed": failed, "recipients": len(recipients)}


def run_report(report: dict) -> dict:
    """Generate + deliver one SITREP now and stamp last_run_at. Best-effort."""
    from modules import sitrep

    op_id = report.get("operation_id")
    if not op_id:
        # No operation targeted — nothing to summarize; skip but stamp the run.
        result = {"sent": 0, "failed": 0, "recipients": 0, "skipped": "no operation_id"}
    else:
        try:
            data = sitrep.build_report_data(op_id)
        except HTTPException:
            result = {"sent": 0, "failed": 0, "recipients": 0, "error": "operation not found"}
            _stamp(report["id"])
            return {"report_id": report["id"], **result}
        # Render once as HTML for email bodies; the structured data goes to webhooks.
        html_body = sitrep.render_html(data)
        result = _deliver(report, data, html_body)
    _stamp(report["id"])
    return {"report_id": report["id"], **result}


def _stamp(report_id: str) -> None:
    with db.get_db() as conn:
        conn.execute(
            "UPDATE scheduled_reports SET last_run_at = ? WHERE id = ?",
            (now_iso(), report_id),
        )
        conn.commit()


def run_due(now: Optional[datetime] = None) -> dict:
    """Run every active, due scheduled report. Returns a per-report summary list."""
    reports = list_reports(active_only=True)["reports"]
    ran = []
    for report in reports:
        if is_due(report, now=now):
            ran.append(run_report(report))
    return {"ran": len(ran), "results": ran}
