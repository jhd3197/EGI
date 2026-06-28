"""Generic entity-lifecycle helpers shared across the server's data modules.

The most-copied backend pattern is the timestamp-guarded last-write-wins upsert
(plan-30 §5.3.1): fetch the stored ``updated_at``, skip the write when the
incoming record is older, otherwise replace the row. ``is_stale`` is that guard
as one tested primitive; ``lww_upsert`` is the full insert-or-replace built on
top of it for entities whose columns map straight from a values dict.

These keep the per-entity modules thin without merging their schemas — each entity
still owns its column list and any side effects (audit/webhook emission).
"""

from typing import Iterable, Mapping, Optional

from timeutil import normalize_ts


def is_stale(cur, table: str, record_id: str, incoming_updated_at: Optional[str],
             *, id_col: str = "id", updated_col: str = "updated_at") -> bool:
    """True when an existing row is newer than ``incoming_updated_at``.

    Callers use this to skip a stale mesh/sync write: the comparison is
    lexicographic over canonical (``normalize_ts``) ISO timestamps, matching the
    hand-written ``incoming < normalize_ts(existing)`` checks across the modules.
    Returns False when there is no existing row or it has no stored timestamp
    (nothing to lose by writing).
    """
    row = cur.execute(
        f"SELECT {updated_col} FROM {table} WHERE {id_col} = ?", (record_id,)
    ).fetchone()
    if not row or not row[0]:
        return False
    incoming = normalize_ts(incoming_updated_at)
    if incoming is None:
        return False
    return incoming < normalize_ts(row[0])


def lww_upsert(cur, table: str, record_id: str, incoming_updated_at: Optional[str],
               values: Mapping, *, id_col: str = "id",
               updated_col: str = "updated_at",
               columns: Optional[Iterable[str]] = None) -> str:
    """Insert-or-replace ``values`` under last-write-wins; returns the outcome.

    Returns ``"skipped"`` when ``is_stale`` says the stored row is newer,
    otherwise ``"written"`` after an ``INSERT OR REPLACE``. ``values`` must
    include ``id_col`` and ``updated_col``. ``columns`` pins the column order;
    when omitted the keys of ``values`` are used. The caller owns the surrounding
    transaction (commit) and any audit/webhook side effects.
    """
    if is_stale(cur, table, record_id, incoming_updated_at,
                id_col=id_col, updated_col=updated_col):
        return "skipped"
    cols = list(columns) if columns is not None else list(values.keys())
    placeholders = ", ".join("?" for _ in cols)
    col_sql = ", ".join(cols)
    cur.execute(
        f"INSERT OR REPLACE INTO {table} ({col_sql}) VALUES ({placeholders})",
        [values[c] for c in cols],
    )
    return "written"
