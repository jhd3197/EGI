"""Timestamp helpers — the single source of truth for UTC time in EGI.

Last-write-wins sync compares ISO-8601 timestamps lexicographically, which only
matches chronological order when every timestamp shares one representation. These
helpers centralize the parse/emit logic that was previously copy-pasted across
``models.py``, ``db.py``, ``migrate.py`` and several dedup/quality modules.

Everything here is best-effort and never raises on bad input, so callers in the
sync/mesh path can stay simple.
"""

from datetime import datetime, timezone
from typing import Optional


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string (e.g. ``2026-01-01T00:00:00+00:00``)."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 string into a ``datetime``; ``None`` on bad/empty input.

    Accepts a trailing ``Z`` (treated as ``+00:00``). Naive results keep their
    naivety — callers that need tz-aware values should compare consistently.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def normalize_ts(ts: Optional[str]) -> Optional[str]:
    """Normalize an ISO-8601 timestamp to a canonical UTC ``Z`` form.

    A mesh relay may send ``2026-01-01T00:00:00+00:00`` while the cloud stored
    ``2026-01-01T00:00:00Z`` — the SAME instant that sorts differently as text.
    We parse and re-emit in UTC with a ``Z`` suffix so equal instants compare
    equal. Unparseable input is returned unchanged (best-effort, never raises).
    """
    if not ts:
        return ts
    parsed = parse_iso(ts)
    if parsed is None:
        return ts
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
