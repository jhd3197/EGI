"""Input sanitization helpers (plan-07 §12).

Two concerns:
  * Length limits on free-text fields so a single record can't be used to dump
    megabytes into the DB or a sync payload.
  * HTML tag stripping as defense in depth. The React PWA already escapes text on
    render, but exports (PFIF/CSV) and any non-React consumer benefit from the
    stored text being tag-free, so a ``<script>`` can never round-trip live.

These are applied via Pydantic field validators on the request models, so a
violation returns a clean ``422`` instead of corrupting data.
"""

import re

# Field length caps. Generous enough for real reports, tight enough that abuse
# (or a runaway client) is rejected.
MAX_NAME = 200
MAX_SHORT = 500      # location, clothes, contact, relation, etc.
MAX_TEXT = 5000      # notes / report body

# Matches an HTML/XML tag: '<' followed by an optional '/' and a letter, through
# the next '>'. Requiring a letter (or '/') right after '<' leaves stray
# comparison characters like "edad < 3 y > 1" untouched.
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def strip_html(value: str) -> str:
    """Remove HTML/XML tags from a string (idempotent)."""
    return _TAG_RE.sub("", value)


def clean_text(value, max_len: int):
    """Validate length and strip HTML tags. Pass-through for None.

    Raises ``ValueError`` (-> 422) when the value exceeds ``max_len`` so the
    caller learns the field was too long instead of it being silently truncated.
    """
    if value is None:
        return None
    text = str(value)
    if len(text) > max_len:
        raise ValueError(f"text exceeds maximum length of {max_len} characters")
    return strip_html(text)
