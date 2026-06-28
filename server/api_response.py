"""Response envelope helpers — one shape for list/success payloads.

The server returns ``{"records": [...]}`` from ~35 list endpoints and
``{"ok": True, ...}`` from ~20 mutations. These helpers make that shape explicit
and consistent without changing the wire contract (the output dicts are
byte-for-byte what the hand-written literals produced).
"""

from typing import Iterable


def records(items: Iterable, **extras) -> dict:
    """``{"records": [...], **extras}`` — the standard list envelope.

    ``extras`` carries the occasional companion keys some endpoints add
    (``count``, ``cursor``, ``total``, …) so they stay in one object.
    """
    return {"records": list(items), **extras}


def ok(**fields) -> dict:
    """``{"ok": True, **fields}`` — the standard success envelope."""
    return {"ok": True, **fields}
