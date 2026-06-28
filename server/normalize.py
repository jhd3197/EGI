"""Text normalization for matching — names, cédulas, phone numbers.

These canonicalizers were re-implemented (slightly differently) across the dedup,
messaging and bot modules. Centralizing them keeps "the same number/name matches"
logic in one place. The functions are pure and never raise.

Note: ``modules/persons.py`` keeps its own ``normalize_cedula`` because it is
coupled to an SQL expression (``_CEDULA_NORM_SQL``) used in the search clause;
that variant strips only a leading V/E to mirror the SQL. The matching/dedup
engines use this module's ``normalize_cedula`` (keeps the nationality letter).
"""

import re
import unicodedata
from typing import Optional


def normalize_name(text: Optional[str]) -> str:
    """Lowercase, strip accents and collapse whitespace for loose comparison."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(no_accents.lower().split())


def normalize_cedula(value: Optional[str], keep_prefix: bool = True) -> str:
    """Canonical cédula key: optional nationality letter + digits, no separators.

    ``V-12.345.678``, ``v12345678``, ``12345678`` all collapse to the same key.
    With ``keep_prefix`` the leading V/E/J/G/P nationality letter is preserved;
    without it only the digits remain. Returns "" when no digits are present.
    """
    if not value:
        return ""
    raw = unicodedata.normalize("NFKD", value).upper()
    letter = ""
    digits = []
    for ch in raw:
        if ch.isdigit():
            digits.append(ch)
        elif ch in "VEJGP" and not digits and not letter:
            letter = ch
    if not digits:
        return ""
    return (letter if keep_prefix else "") + "".join(digits)


def normalize_phone(value: Optional[str], strategy: str = "match") -> str:
    """Canonical phone key under the requested ``strategy``.

    - ``match`` (default): last 10 digits, "" when fewer than 7 — the loose
      cross-format key used by deduplication.
    - ``plus``: digits with an optional leading ``+`` kept (SMS/check-in).
    - ``whatsapp``: strip a ``whatsapp:`` address prefix, then ``plus``.
    - ``digits``: digits only, no ``+`` (provider payloads that want bare numbers).
    """
    if not value:
        return ""
    if strategy == "whatsapp":
        value = value.replace("whatsapp:", "").strip()
        return re.sub(r"[^0-9+]", "", value)
    if strategy == "plus":
        return re.sub(r"[^0-9+]", "", value)
    if strategy == "digits":
        return re.sub(r"[^\d]", "", value)
    # "match": national significant number (last 10 digits) for loose matching.
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) < 7:
        return ""
    return digits[-10:]
