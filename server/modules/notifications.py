"""Preference-aware notification gating (plan-24 Phase 4).

The single place that answers "should this recipient get this notification?"
before any push/SMS/email goes out. It consults the recipient's preferences:

  * Is the **category** enabled for notifications?
  * Is the recipient still **subscribed** (not muted) to the operation?
  * Is the record within the recipient's **near-me radius**?
  * Are we inside the recipient's **quiet hours** (non-critical categories only)?

Two escape hatches keep life-safety alerts flowing:
  * ``force=True`` — an own-record match ("your missing person was found") always
    notifies, whatever the toggles say (plan-24 Phase 7).
  * Critical categories (``people``, ``broadcasts``) ignore quiet hours.

Anonymous recipients (a push subscription with no ``user_id``) stay permissive:
we cannot read preferences we do not have, so we never silently drop them.
"""

from datetime import datetime, timezone
from typing import List, Optional

import db
from models import CRITICAL_CATEGORIES
from modules import preferences


def _within_radius(settings: dict, lat: Optional[float], lon: Optional[float]) -> bool:
    """True when a record is inside the user's near-me radius (or no radius set).

    A record without coordinates is always kept — we can't place it, so we don't
    hide it. Mirrors the client-side filter in frontend/src/lib/view.js.
    """
    radius = settings.get("radius_meters") if settings else None
    home_lat = settings.get("home_lat") if settings else None
    home_lon = settings.get("home_lon") if settings else None
    if not radius or home_lat is None or home_lon is None:
        return True
    if lat is None or lon is None:
        return True
    return _haversine_m(home_lat, home_lon, lat, lon) <= radius


def _haversine_m(a_lat, a_lon, b_lat, b_lon) -> float:
    import math

    r = 6371000.0
    d_lat = math.radians(b_lat - a_lat)
    d_lon = math.radians(b_lon - a_lon)
    h = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(d_lon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def in_quiet_hours(settings: dict, now: Optional[datetime] = None) -> bool:
    """True if the current UTC hour is inside the user's quiet-hours window.

    The window may wrap midnight (e.g. 22→7). No window set → never quiet.
    """
    start = settings.get("quiet_hours_start") if settings else None
    end = settings.get("quiet_hours_end") if settings else None
    if start is None or end is None:
        return False
    hour = (now or datetime.now(timezone.utc)).hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # wraps midnight


def allows(
    user_id: Optional[str],
    category: str,
    *,
    operation_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    force: bool = False,
) -> bool:
    """The notification decision for one recipient. See module docstring."""
    if force:
        return True
    if not user_id:
        return True  # anonymous device: stay permissive
    if not preferences.should_notify(user_id, category):
        return False
    from modules import subscriptions
    if subscriptions.is_muted(user_id, operation_id):
        return False
    settings = preferences.get_settings(user_id)
    if not _within_radius(settings, lat, lon):
        return False
    if category not in CRITICAL_CATEGORIES:
        if in_quiet_hours(settings):
            return False
        # Batch/digest users (e.g. diaspora moderators) opt out of the immediate
        # non-critical flood; a digest job delivers these later (future work).
        if settings.get("batch_notifications"):
            return False
    return True


def filter_push_subscriptions(
    subs: List[dict],
    category: str,
    *,
    operation_id: Optional[str] = None,
    force: bool = False,
) -> List[dict]:
    """Keep only the push subscriptions whose owner allows this category."""
    return [
        s for s in subs
        if allows(s.get("user_id"), category, operation_id=operation_id, force=force)
    ]


def send_test(user_id: str) -> dict:
    """Send a test notification to the user's own push subscriptions (Phase 4).

    Bypasses the preference gate on purpose — the user explicitly asked to verify
    delivery. Returns ``{recipients, sent, failed}``; ``recipients=0`` means the
    user has no registered push device.
    """
    from modules import messaging, providers

    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM push_subscriptions WHERE active = 1 AND user_id = ?",
            (user_id,),
        ).fetchall()
    subs = [db.row_to_dict(r) for r in rows]
    cfg = messaging.get_provider_config("push")
    title = "EGI"
    body = "Test notification — EGI"
    sent, failed = 0, 0
    for sub in subs:
        result = providers.send_push(sub, title, body, cfg)
        messaging.record_message(
            channel="push",
            direction="outbound",
            to_address=sub.get("endpoint"),
            subject=title,
            body=body,
            status=result["status"],
            error=result.get("error"),
            external_id=result.get("external_id"),
            locale=sub.get("locale"),
        )
        if result["status"] == "sent":
            sent += 1
        else:
            failed += 1
    return {"recipients": len(subs), "sent": sent, "failed": failed}
