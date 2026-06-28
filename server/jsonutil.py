"""JSON list encode/decode with safe defaults.

Several entity modules store small arrays (services, supply needs, photos, …) as
JSON TEXT columns and re-implement the same defensive encode/decode. These two
helpers are that pattern, once: ``dumps`` returns ``None`` for ``None`` (so the
column stays NULL) and ``loads_list`` always returns a ``list`` even on garbage.
"""

import json
from typing import Optional


def dumps(value) -> Optional[str]:
    """JSON-encode an iterable as a list; ``None`` passes through as ``None``.

    Returns ``None`` (not ``"null"``) when the value can't be encoded, so the
    caller can leave the DB column NULL rather than storing broken JSON.
    """
    if value is None:
        return None
    try:
        return json.dumps(list(value))
    except (TypeError, ValueError):
        return None


def loads_list(raw) -> list:
    """Decode a JSON-TEXT column into a ``list``; ``[]`` for empty/garbage/non-list."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []
