"""Versioned action plans and their tasks (plan-09 §4-6).

Each operation (`events` row) can have multiple action-plan versions; at most one
is ``is_active`` at a time. Creating a plan seeds tasks — either the default
``task_templates`` list or a copy of the previous version's tasks. Tasks have a
small state machine (pending → in_progress → done, plus cancelled), an optional
assignee and free-text notes, and every mutation writes to the audit log.
"""

import uuid
from typing import Optional

from fastapi import HTTPException

import db
from models import now_iso, validate_task_state


# ── Action plans ─────────────────────────────────────────────────────────────

def _operation_exists(conn, event_id: str) -> bool:
    return conn.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone() is not None


def list_plans(event_id: str) -> dict:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM action_plans WHERE event_id = ? AND deleted = 0 "
            "ORDER BY version DESC",
            (event_id,),
        ).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def get_plan(plan_id: str, conn=None) -> Optional[dict]:
    if conn is not None:
        row = conn.execute(
            "SELECT * FROM action_plans WHERE id = ? AND deleted = 0", (plan_id,)
        ).fetchone()
        return db.row_to_dict(row) if row else None
    with db.get_db() as c:
        return get_plan(plan_id, c)


def create_plan(event_id: str, data, actor: str = "system") -> dict:
    now = now_iso()
    plan_id = f"egi-plan-{uuid.uuid4().hex[:8]}"
    with db.get_db() as conn:
        if not _operation_exists(conn, event_id):
            raise HTTPException(status_code=404, detail="Operation not found")
        # Next version = max existing (incl. soft-deleted, to keep UNIQUE intact) + 1.
        row = conn.execute(
            "SELECT MAX(version) AS v FROM action_plans WHERE event_id = ?", (event_id,)
        ).fetchone()
        version = (row["v"] or 0) + 1
        # First plan for the operation activates automatically; later versions are
        # created inactive and a commander activates them explicitly.
        active_count = conn.execute(
            "SELECT COUNT(*) AS n FROM action_plans WHERE event_id = ? AND deleted = 0",
            (event_id,),
        ).fetchone()["n"]
        is_active = 1 if active_count == 0 else 0
        if is_active:
            conn.execute(
                "UPDATE action_plans SET is_active = 0, updated_at = ? WHERE event_id = ?",
                (now, event_id),
            )
        conn.execute(
            "INSERT INTO action_plans "
            "(id, event_id, version, description, is_active, deleted, created_by, "
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)",
            (plan_id, event_id, version, data.description, is_active, actor, now, now),
        )

        # Seed tasks: copy previous version, or default templates, or nothing.
        if getattr(data, "copy_from_previous", False):
            prev = conn.execute(
                "SELECT * FROM action_plans WHERE event_id = ? AND id != ? AND deleted = 0 "
                "ORDER BY version DESC LIMIT 1",
                (event_id, plan_id),
            ).fetchone()
            if prev:
                _copy_tasks(conn, prev["id"], plan_id, now)
        elif getattr(data, "seed_defaults", True):
            _seed_default_tasks(conn, plan_id, now)
        conn.commit()
        plan = get_plan(plan_id, conn)
    _audit(actor, "action_plan_create", plan_id, f"event={event_id} v{version}")
    return plan


def _seed_default_tasks(conn, plan_id: str, now: str) -> None:
    templates = conn.execute(
        "SELECT title, description, sort_order FROM task_templates WHERE active = 1 "
        "ORDER BY sort_order ASC"
    ).fetchall()
    for t in templates:
        conn.execute(
            "INSERT INTO action_plan_tasks "
            "(id, action_plan_id, title, description, state, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)",
            (f"egi-task-{uuid.uuid4().hex[:8]}", plan_id, t["title"], t["description"],
             t["sort_order"], now, now),
        )


def _copy_tasks(conn, src_plan_id: str, dst_plan_id: str, now: str) -> None:
    rows = conn.execute(
        "SELECT title, description, assignee_id, sort_order FROM action_plan_tasks "
        "WHERE action_plan_id = ? ORDER BY sort_order ASC",
        (src_plan_id,),
    ).fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO action_plan_tasks "
            "(id, action_plan_id, assignee_id, title, description, state, sort_order, "
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
            (f"egi-task-{uuid.uuid4().hex[:8]}", dst_plan_id, r["assignee_id"],
             r["title"], r["description"], r["sort_order"], now, now),
        )


def activate_plan(plan_id: str, actor: str = "system") -> dict:
    now = now_iso()
    with db.get_db() as conn:
        plan = get_plan(plan_id, conn)
        if not plan:
            raise HTTPException(status_code=404, detail="Action plan not found")
        conn.execute(
            "UPDATE action_plans SET is_active = 0, updated_at = ? WHERE event_id = ?",
            (now, plan["event_id"]),
        )
        conn.execute(
            "UPDATE action_plans SET is_active = 1, updated_at = ? WHERE id = ?",
            (now, plan_id),
        )
        conn.commit()
        plan = get_plan(plan_id, conn)
    _audit(actor, "action_plan_activate", plan_id, f"event={plan['event_id']}")
    return plan


def update_plan(plan_id: str, data, actor: str = "system") -> dict:
    now = now_iso()
    with db.get_db() as conn:
        if not get_plan(plan_id, conn):
            raise HTTPException(status_code=404, detail="Action plan not found")
        if data.description is not None:
            conn.execute(
                "UPDATE action_plans SET description = ?, updated_at = ? WHERE id = ?",
                (data.description, now, plan_id),
            )
            conn.commit()
        plan = get_plan(plan_id, conn)
    _audit(actor, "action_plan_update", plan_id)
    return plan


def delete_plan(plan_id: str, actor: str = "system") -> dict:
    """Soft-delete a plan. An active plan cannot be deleted (409) — deactivate or
    activate another version first, so an operation never loses its active plan
    silently."""
    now = now_iso()
    with db.get_db() as conn:
        plan = get_plan(plan_id, conn)
        if not plan:
            raise HTTPException(status_code=404, detail="Action plan not found")
        if plan["is_active"]:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete the active plan; activate another version first",
            )
        conn.execute(
            "UPDATE action_plans SET deleted = 1, updated_at = ? WHERE id = ?",
            (now, plan_id),
        )
        conn.commit()
    _audit(actor, "action_plan_delete", plan_id)
    return {"ok": True, "id": plan_id}


# ── Tasks ────────────────────────────────────────────────────────────────────

def get_task(task_id: str, conn=None) -> Optional[dict]:
    if conn is not None:
        row = conn.execute(
            "SELECT * FROM action_plan_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return db.row_to_dict(row) if row else None
    with db.get_db() as c:
        return get_task(task_id, c)


def list_tasks(plan_id: str) -> dict:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM action_plan_tasks WHERE action_plan_id = ? "
            "ORDER BY sort_order ASC, created_at ASC",
            (plan_id,),
        ).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def create_task(plan_id: str, data, actor: str = "system") -> dict:
    if not data.title:
        raise HTTPException(status_code=400, detail="title is required")
    if not validate_task_state(data.state):
        raise HTTPException(status_code=400, detail=f"invalid state: {data.state}")
    now = now_iso()
    task_id = f"egi-task-{uuid.uuid4().hex[:8]}"
    state = data.state or "pending"
    completed_at = now if state == "done" else None
    completed_by = actor if state == "done" else None
    with db.get_db() as conn:
        if not get_plan(plan_id, conn):
            raise HTTPException(status_code=404, detail="Action plan not found")
        conn.execute(
            "INSERT INTO action_plan_tasks "
            "(id, action_plan_id, assignee_id, title, description, state, sort_order, "
            " notes, due_at, completed_at, completed_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, plan_id, data.assignee_id, data.title, data.description, state,
             int(data.sort_order or 0), data.notes, data.due_at, completed_at,
             completed_by, now, now),
        )
        conn.commit()
        task = get_task(task_id, conn)
    _audit(actor, "task_create", task_id, f"plan={plan_id}")
    return task


# Columns a PATCH may set directly (excluding state, which has side effects).
_TASK_PATCH_FIELDS = ["title", "description", "assignee_id", "sort_order", "notes", "due_at"]


def update_task(task_id: str, data, actor: str = "system") -> dict:
    fields = data.model_dump(exclude_unset=True)
    if "state" in fields and not validate_task_state(fields["state"]):
        raise HTTPException(status_code=400, detail=f"invalid state: {fields['state']}")
    now = now_iso()
    with db.get_db() as conn:
        existing = get_task(task_id, conn)
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")
        sets, params = [], []
        for col in _TASK_PATCH_FIELDS:
            if col in fields:
                val = fields[col]
                if col == "sort_order" and val is not None:
                    val = int(val)
                sets.append(f"{col} = ?")
                params.append(val)
        if "state" in fields:
            new_state = fields["state"]
            sets.append("state = ?")
            params.append(new_state)
            # Stamp / clear completion metadata as the task enters or leaves `done`.
            if new_state == "done" and existing["state"] != "done":
                sets.append("completed_at = ?")
                params.append(now)
                sets.append("completed_by = ?")
                params.append(actor)
            elif new_state != "done" and existing["state"] == "done":
                sets.append("completed_at = NULL")
                sets.append("completed_by = NULL")
        if sets:
            sets.append("updated_at = ?")
            params.append(now)
            params.append(task_id)
            conn.execute(
                f"UPDATE action_plan_tasks SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
        task = get_task(task_id, conn)
    _audit(actor, "task_update", task_id, f"state={fields.get('state', existing['state'])}")
    return task


def delete_task(task_id: str, actor: str = "system") -> dict:
    with db.get_db() as conn:
        if not get_task(task_id, conn):
            raise HTTPException(status_code=404, detail="Task not found")
        conn.execute("DELETE FROM action_plan_tasks WHERE id = ?", (task_id,))
        conn.commit()
    _audit(actor, "task_delete", task_id)
    return {"ok": True, "id": task_id}


def _audit(actor: str, action: str, target_id: str, detail: str = "") -> None:
    from modules import audit

    target_type = "task" if action.startswith("task") else "action_plan"
    audit.log_action(actor, action, target_type, target_id, detail=detail)
