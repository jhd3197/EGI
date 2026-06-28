"""Record-ID generation — one place for the ``prefix-hex`` pattern.

Modules across the server mint ids as ``f"{prefix}-{uuid.uuid4().hex[:N]}"`` with
varying prefixes and lengths. ``new_id`` centralizes that so the shape is
consistent and the next entity doesn't copy-paste a fifteenth variant.
"""

import uuid


def new_id(prefix: str, length: int = 8) -> str:
    """Return ``"{prefix}-{hex}"`` where ``hex`` is ``length`` random hex chars.

    ``length`` is clamped to the 32 hex chars a UUID4 provides.
    """
    n = max(1, min(int(length), 32))
    return f"{prefix}-{uuid.uuid4().hex[:n]}"
