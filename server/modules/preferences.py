"""User preferences & per-category subscription logic (plan-24 Phase 1).

A unified layer so each user controls three independent dimensions per content
category (people, animals, shelters, hazards, supplies, operations, broadcasts):

* **display**     — show or hide the category in the PWA UI.
* **notify**      — receive push/SMS/email alerts for this category.
* **mesh_relay**  — forward records of this category over the Bluetooth mesh.

Defaults live here (``default_category``), so an *absent* row means "use the
default" — we persist only what the user has actually changed. Reads merge the
stored rows over the defaults so callers always get a complete picture.

Upserts are timestamp-guarded last-write-wins on ``updated_at`` (same model as
``/sync``): a stale change synced from an old device cannot clobber a newer one.

The ``should_display`` / ``should_notify`` / ``should_relay`` helpers are the
surface other modules (notifications, mesh export, UI) consult; they degrade to
the default (permissive) when no row exists, so the system works for guests and
users who never opened Settings.
"""

from typing import List, Optional

import db
from models import (
    CONTENT_CATEGORIES,
    DEFAULT_NOTIFY_CATEGORIES,
    PreferencesUpdate,
    normalize_ts,
    now_iso,
)


def default_category(category: str) -> dict:
    """The default preference for a category: display+relay on, notify per policy."""
    return {
        "category": category,
        "display_enabled": 1,
        "notify_enabled": 1 if category in DEFAULT_NOTIFY_CATEGORIES else 0,
        "mesh_relay_enabled": 1,
        "radius_meters": None,
        "updated_at": None,
    }


def default_settings() -> dict:
    """The default global (non-category) settings for a user."""
    return {
        "radius_meters": None,
        "home_lat": None,
        "home_lon": None,
        "quiet_hours_start": None,
        "quiet_hours_end": None,
        "batch_notifications": 0,
        "updated_at": None,
    }


def get_preferences(user_id: str) -> dict:
    """Return a user's full preferences: every category merged over defaults.

    The shape is ``{"categories": {cat: {...}}, "settings": {...}}``. Categories
    the user never touched come back at their defaults, so the UI can render the
    whole grid from one call.
    """
    cats = {c: default_category(c) for c in sorted(CONTENT_CATEGORIES)}
    settings = default_settings()
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
        ).fetchall()
        for row in rows:
            d = db.row_to_dict(row)
            cat = d.get("category")
            if cat in cats:
                cats[cat] = {
                    "category": cat,
                    "display_enabled": d.get("display_enabled"),
                    "notify_enabled": d.get("notify_enabled"),
                    "mesh_relay_enabled": d.get("mesh_relay_enabled"),
                    "radius_meters": d.get("radius_meters"),
                    "updated_at": d.get("updated_at"),
                }
        srow = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if srow:
            sd = db.row_to_dict(srow)
            sd.pop("user_id", None)
            settings = sd
    return {"categories": cats, "settings": settings}


def _get_category_row(conn, user_id: str, category: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM user_preferences WHERE user_id = ? AND category = ?",
        (user_id, category),
    ).fetchone()
    return db.row_to_dict(row) if row else None


def set_preferences(user_id: str, patch: PreferencesUpdate) -> dict:
    """Upsert category preferences and/or global settings for a user.

    Timestamp-guarded last-write-wins per row: an incoming change with an
    ``updated_at`` older than the stored row is skipped. Returns the full,
    freshly-merged preferences plus a ``skipped`` count of stale rows ignored.
    """
    now = now_iso()
    skipped = 0
    with db.get_db() as conn:
        for cp in patch.categories or []:
            if cp.category not in CONTENT_CATEGORIES:
                continue
            existing = _get_category_row(conn, user_id, cp.category)
            ts = normalize_ts(cp.updated_at) or now
            if existing and existing.get("updated_at"):
                if normalize_ts(ts) < normalize_ts(existing["updated_at"]):
                    skipped += 1
                    continue
            base = existing or default_category(cp.category)
            display = cp.display_enabled if cp.display_enabled is not None else base["display_enabled"]
            notify = cp.notify_enabled if cp.notify_enabled is not None else base["notify_enabled"]
            relay = cp.mesh_relay_enabled if cp.mesh_relay_enabled is not None else base["mesh_relay_enabled"]
            radius = cp.radius_meters if cp.radius_meters is not None else base.get("radius_meters")
            conn.execute(
                "INSERT INTO user_preferences "
                "(user_id, category, display_enabled, notify_enabled, mesh_relay_enabled, radius_meters, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, category) DO UPDATE SET "
                "display_enabled=excluded.display_enabled, notify_enabled=excluded.notify_enabled, "
                "mesh_relay_enabled=excluded.mesh_relay_enabled, radius_meters=excluded.radius_meters, "
                "updated_at=excluded.updated_at",
                (user_id, cp.category, int(bool(display)), int(bool(notify)),
                 int(bool(relay)), radius, ts),
            )
        if patch.settings is not None:
            s = patch.settings
            srow = conn.execute(
                "SELECT updated_at FROM user_settings WHERE user_id = ?", (user_id,)
            ).fetchone()
            ts = normalize_ts(s.updated_at) or now
            if srow and srow["updated_at"] and normalize_ts(ts) < normalize_ts(srow["updated_at"]):
                skipped += 1
            else:
                conn.execute(
                    "INSERT INTO user_settings "
                    "(user_id, radius_meters, home_lat, home_lon, quiet_hours_start, "
                    "quiet_hours_end, batch_notifications, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET "
                    "radius_meters=excluded.radius_meters, home_lat=excluded.home_lat, "
                    "home_lon=excluded.home_lon, quiet_hours_start=excluded.quiet_hours_start, "
                    "quiet_hours_end=excluded.quiet_hours_end, "
                    "batch_notifications=excluded.batch_notifications, updated_at=excluded.updated_at",
                    (user_id, s.radius_meters, s.home_lat, s.home_lon,
                     s.quiet_hours_start, s.quiet_hours_end,
                     int(bool(s.batch_notifications)), ts),
                )
        conn.commit()
    result = get_preferences(user_id)
    result["skipped"] = skipped
    return result


# ── Decision helpers (consulted by other modules) ─────────────────────────────
#
# Each degrades to the category default when no row exists, so guests and
# never-configured users get sensible permissive behaviour.

def _category_pref(user_id: Optional[str], category: str) -> dict:
    if not user_id or category not in CONTENT_CATEGORIES:
        return default_category(category)
    with db.get_db() as conn:
        row = _get_category_row(conn, user_id, category)
    if not row:
        return default_category(category)
    return row


def should_display(user_id: Optional[str], category: str) -> bool:
    return bool(_category_pref(user_id, category).get("display_enabled", 1))


def should_notify(user_id: Optional[str], category: str) -> bool:
    return bool(_category_pref(user_id, category).get("notify_enabled", 0))


def should_relay(user_id: Optional[str], category: str) -> bool:
    return bool(_category_pref(user_id, category).get("mesh_relay_enabled", 1))


def get_settings(user_id: Optional[str]) -> dict:
    """Return a user's global settings merged over defaults."""
    if not user_id:
        return default_settings()
    with db.get_db() as conn:
        srow = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
    if not srow:
        return default_settings()
    sd = db.row_to_dict(srow)
    sd.pop("user_id", None)
    return sd
