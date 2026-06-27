"""Sync logic: timestamp-guarded last-write-wins upload + since-download."""

from typing import Optional

from fastapi import HTTPException

import db
from models import SyncPayload, now_iso, normalize_ts, validate_status
from modules import audit
from modules.reports import upsert_report


def sync_upload(payload: SyncPayload) -> dict:
    if not isinstance(payload.records, list):
        raise HTTPException(status_code=400, detail="records must be an array")

    now = now_iso()
    skipped = 0
    # New person ids created this batch — history is logged AFTER commit so the
    # append-only audit writes don't contend with the open write transaction
    # (a second SQLite connection mid-transaction risks a write lock).
    created: list = []
    with db.get_db() as conn:
        cur = conn.cursor()
        for r in payload.records:
            if not r.id:
                raise HTTPException(status_code=400, detail="record id is required")
            if not validate_status(r.status):
                raise HTTPException(status_code=400, detail=f"invalid status: {r.status}")
            # Timestamp-guarded last-write-wins: the same record reaches the cloud
            # via many mesh paths and often OUT OF ORDER, so a stale relay must not
            # clobber a newer update. Compare updated_at (ISO-8601 UTC sorts
            # lexicographically). normalize_ts() canonicalizes 'Z' vs '+00:00' so
            # equal instants in different offsets don't misorder. Ties replace so
            # equal-timestamp corrections still apply.
            incoming_updated = normalize_ts(r.updatedAt or now)
            created_at = normalize_ts(r.createdAt or now)
            existing = cur.execute(
                "SELECT updated_at, merged_into, retained_until FROM persons WHERE id = ?",
                (r.id,),
            ).fetchone()
            if existing and existing[0] and incoming_updated < normalize_ts(existing[0]):
                skipped += 1
                continue
            if existing is None:
                created.append((r.id, r.source or "web"))
            # Preserve a server-side merge decision: INSERT OR REPLACE rewrites the
            # whole row, so without this a client re-syncing the pre-merge copy would
            # silently un-merge a moderated duplicate. Incoming wins only if it set one.
            merged_into = r.merged_into or (existing["merged_into"] if existing else None)
            # Retention is a server-local operator decision and is never sent by
            # clients, so always carry forward the stored value across upserts
            # (INSERT OR REPLACE would otherwise reset it to NULL).
            retained_until = existing["retained_until"] if existing else None
            values = (
                r.id,
                r.disaster_id,
                r.name,
                r.status,
                r.gender,
                r.age,
                r.location,
                r.last_seen_date,
                r.clothes,
                r.notes,
                r.contact,
                r.reporter_name,
                r.reporter_relation,
                r.reporter_country,
                r.reported_by,
                r.source or "web",
                r.provenance,
                r.image_path,
                r.ocr_text,
                r.extracted_json,
                r.confidence,
                r.reviewed if r.reviewed is not None else 0,
                r.given_name,
                r.family_name,
                r.cedula,
                r.sex,
                r.photo_url,
                r.last_known_location,
                r.origin_device,
                r.hop_count if r.hop_count is not None else 0,
                merged_into,
                retained_until,
                r.lat,
                r.lon,
                created_at,
                incoming_updated,
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO persons
                (id, disaster_id, name, status, gender, age, location, last_seen_date,
                 clothes, notes, contact, reporter_name, reporter_relation, reporter_country,
                 reported_by, source, provenance, image_path, ocr_text, extracted_json,
                 confidence, reviewed, given_name, family_name, cedula, sex, photo_url,
                 last_known_location, origin_device, hop_count, merged_into, retained_until,
                 lat, lon, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

        reports = payload.reports or []
        reports_skipped = 0
        for rep in reports:
            if not upsert_report(cur, rep, now):
                reports_skipped += 1

        conn.commit()

    # Append-only creation history (best-effort, post-commit).
    for rec_id, src in created:
        audit.log_history(rec_id, "create", actor="sync", source=src)

    saved = len(payload.records) - skipped
    saved_reports = len(reports) - reports_skipped
    log_sync(direction="in", record_count=saved,
             detail=f"persons={saved}/{len(payload.records)} "
                    f"reports={saved_reports}/{len(reports)} (stale skipped: "
                    f"{skipped}+{reports_skipped})")
    return {
        "saved": saved,
        "reports": saved_reports,
        "skipped": skipped + reports_skipped,
    }


def sync_download(since: Optional[str] = None) -> dict:
    since = since or "1970-01-01T00:00:00Z"
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM persons WHERE updated_at > ? ORDER BY updated_at ASC", (since,)
        ).fetchall()
        # Reports (PFIF notes) ride alongside persons so a device that only ever
        # reaches the cloud (never the mesh) still receives notes from other peers.
        # Additive key: older clients that read only `records` keep working.
        report_rows = conn.execute(
            "SELECT * FROM reports WHERE updated_at > ? ORDER BY updated_at ASC", (since,)
        ).fetchall()
        return {
            "records": [db.row_to_dict(r) for r in rows],
            "reports": [db.row_to_dict(r) for r in report_rows],
        }


def operations_download(since: Optional[str] = None) -> dict:
    """Read-only pull of operational data for offline field use (plan-09 §8).

    Returns operations (events), their action plans, and tasks updated after
    ``since``. Operation/plan data is server-managed, so this side is read-only;
    only task state syncs back up (``operations_upload``).
    """
    since = since or "1970-01-01T00:00:00Z"
    with db.get_db() as conn:
        ops = conn.execute(
            "SELECT * FROM events WHERE updated_at > ? ORDER BY updated_at ASC", (since,)
        ).fetchall()
        plans = conn.execute(
            "SELECT * FROM action_plans WHERE updated_at > ? AND deleted = 0 "
            "ORDER BY updated_at ASC",
            (since,),
        ).fetchall()
        tasks = conn.execute(
            "SELECT * FROM action_plan_tasks WHERE updated_at > ? ORDER BY updated_at ASC",
            (since,),
        ).fetchall()
        return {
            "operations": [db.row_to_dict(r) for r in ops],
            "action_plans": [db.row_to_dict(r) for r in plans],
            "tasks": [db.row_to_dict(r) for r in tasks],
        }


def operations_upload(payload) -> dict:
    """Apply field-originated task state changes with timestamp-guarded LWW.

    Mirrors the persons sync guard: an incoming change older than the stored
    ``updated_at`` is skipped so a stale relay can't clobber a newer edit. Only
    pre-existing tasks are updated (plans/tasks are server-created); unknown ids
    are skipped. Setting state to ``done`` stamps completion metadata if absent.
    """
    from models import validate_task_state

    now = now_iso()
    saved = skipped = 0
    with db.get_db() as conn:
        cur = conn.cursor()
        for t in payload.tasks:
            if t.state is not None and not validate_task_state(t.state):
                raise HTTPException(status_code=400, detail=f"invalid state: {t.state}")
            existing = cur.execute(
                "SELECT state, updated_at FROM action_plan_tasks WHERE id = ?", (t.id,)
            ).fetchone()
            if existing is None:
                skipped += 1
                continue
            incoming = normalize_ts(t.updatedAt or now)
            if existing["updated_at"] and incoming < normalize_ts(existing["updated_at"]):
                skipped += 1
                continue
            sets, params = [], []
            for col in ("state", "assignee_id", "notes"):
                val = getattr(t, col)
                if val is not None:
                    sets.append(f"{col} = ?")
                    params.append(val)
            # Completion metadata follows the state, mirroring update_task.
            if t.state == "done" and existing["state"] != "done":
                sets.append("completed_at = ?")
                params.append(t.completed_at or now)
                sets.append("completed_by = ?")
                params.append(t.completed_by or "sync")
            elif t.state is not None and t.state != "done" and existing["state"] == "done":
                sets.append("completed_at = NULL")
                sets.append("completed_by = NULL")
            if not sets:
                skipped += 1
                continue
            sets.append("updated_at = ?")
            params.append(incoming)
            params.append(t.id)
            cur.execute(
                f"UPDATE action_plan_tasks SET {', '.join(sets)} WHERE id = ?", params
            )
            saved += 1
        conn.commit()
    log_sync(direction="in", record_count=saved,
             detail=f"tasks={saved}/{len(payload.tasks)} (stale skipped: {skipped})")
    return {"saved": saved, "skipped": skipped}


def log_sync(direction: str, record_count: int, detail: str = "",
             peer: Optional[str] = None, origin_device: Optional[str] = None) -> None:
    """Best-effort sync audit row. Never raises so it can't break a sync."""
    try:
        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO sync_log
                (direction, peer, origin_device, record_count, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (direction, peer, origin_device, record_count, detail, now_iso()),
            )
            conn.commit()
    except Exception:
        pass
