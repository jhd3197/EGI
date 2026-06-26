"""PFIF-aligned import/export for EGI.

EGI's sync envelope is already PFIF-shaped; this module makes it explicit so
operators can move data in and out.

- **JSON** is the canonical, lossless format and matches the ``/sync`` payload
  (``{"records": [...persons...], "reports": [...]}``) with person timestamps in
  camelCase ``createdAt``/``updatedAt`` so an export file can be POSTed straight
  to ``/sync``. A ``_comment`` field carries the review-before-sharing header
  (plan §12) without breaking JSON validity.
- **XML** is a best-effort PFIF 1.4 serialization: canonical PFIF tags for the
  mappable fields plus ``egi:`` extension tags for everything else, so it still
  round-trips through this module without losing provenance.

Imports land as ``source='pfif_import'`` with ``reviewed=0`` (unless
``--auto-approve``) and skip exact ``id`` + ``origin_device`` duplicates.
"""

import json
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

import db
from models import VALID_STATUSES, now_iso

EXPORT_HEADER = (
    "EGI export — review before sharing; contains personal data from a crisis context."
)

PFIF_NS = "http://zesty.ca/pfif/1.4"
EGI_NS = "http://egi.local/ext"

# our person key -> canonical PFIF 1.4 person tag (everything else -> egi: ext)
PFIF_PERSON = {
    "id": "person_record_id",
    "name": "full_name",
    "given_name": "given_name",
    "family_name": "family_name",
    "sex": "sex",
    "age": "age",
    "location": "home_city",
    "photo_url": "photo_url",
}
PFIF_PERSON_REV = {v: k for k, v in PFIF_PERSON.items()}

PFIF_NOTE = {
    "id": "note_record_id",
    "person_id": "person_record_id",
    "author_name": "author_name",
    "note": "text",
}
PFIF_NOTE_REV = {v: k for k, v in PFIF_NOTE.items()}

# Person fields that should be coerced to numbers on import.
_INT_FIELDS = {"age", "hop_count", "reviewed"}
_FLOAT_FIELDS = {"confidence"}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _query_persons(since, disaster_id, event_id, reviewed) -> list:
    sql = "SELECT * FROM persons WHERE 1=1"
    params: list = []
    if since:
        sql += " AND updated_at > ?"
        params.append(since)
    if reviewed is not None:
        sql += " AND reviewed = ?"
        params.append(reviewed)

    disaster_ids = []
    if disaster_id:
        disaster_ids.append(disaster_id)
    if event_id:
        disaster_ids.append(event_id)
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT tag FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            if row and row[0]:
                disaster_ids.append(row[0])
    if disaster_ids:
        placeholders = ", ".join("?" for _ in disaster_ids)
        sql += f" AND disaster_id IN ({placeholders})"
        params.extend(disaster_ids)

    sql += " ORDER BY updated_at ASC"
    with db.get_db() as conn:
        return [db.row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def _query_reports(person_ids: list) -> list:
    if not person_ids:
        return []
    placeholders = ", ".join("?" for _ in person_ids)
    with db.get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM reports WHERE person_id IN ({placeholders}) "
            "ORDER BY created_at ASC",
            person_ids,
        ).fetchall()
        return [db.row_to_dict(r) for r in rows]


def _to_sync_shape(row: dict) -> dict:
    """Rename created_at/updated_at -> createdAt/updatedAt so the JSON matches
    the /sync PersonRecord/ReportRecord schema (other fields stay as-is)."""
    out = dict(row)
    if "created_at" in out:
        out["createdAt"] = out.pop("created_at")
    if "updated_at" in out:
        out["updatedAt"] = out.pop("updated_at")
    return out


def export_records(since: Optional[str] = None, disaster_id: Optional[str] = None,
                   event_id: Optional[str] = None, reviewed: Optional[int] = None,
                   fmt: str = "json") -> Tuple[str, dict]:
    db.init_db()
    persons = _query_persons(since, disaster_id, event_id, reviewed)
    reports = _query_reports([p["id"] for p in persons])
    counts = {"records": len(persons), "reports": len(reports)}

    if fmt == "xml":
        return _to_xml(persons, reports), counts
    payload = {
        "_comment": EXPORT_HEADER,
        "records": [_to_sync_shape(p) for p in persons],
        "reports": [_to_sync_shape(r) for r in reports],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False), counts


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _emit_fields(lines, row, std_map, indent):
    for k, v in _to_sync_shape(row).items():
        if v is None:
            continue
        tag = f"pfif:{std_map[k]}" if k in std_map else f"egi:{k}"
        lines.append(f"{indent}<{tag}>{_xml_escape(str(v))}</{tag}>")


def _to_xml(persons: list, reports: list) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- {EXPORT_HEADER} -->",
        f'<pfif:pfif xmlns:pfif="{PFIF_NS}" xmlns:egi="{EGI_NS}">',
    ]
    for p in persons:
        lines.append("  <pfif:person>")
        _emit_fields(lines, p, PFIF_PERSON, "    ")
        lines.append("  </pfif:person>")
    for r in reports:
        lines.append("  <pfif:note>")
        _emit_fields(lines, r, PFIF_NOTE, "    ")
        lines.append("  </pfif:note>")
    lines.append("</pfif:pfif>")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _strip_comment_lines(text: str) -> str:
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    )


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]  # strip {namespace}


def _from_xml(text: str) -> Tuple[list, list]:
    root = ET.fromstring(text)
    persons, reports = [], []
    for el in root:
        kind = _local(el.tag)
        rec = {}
        for child in el:
            name = _local(child.tag)
            val = child.text
            if kind == "person":
                key = PFIF_PERSON_REV.get(name, name)
            else:
                key = PFIF_NOTE_REV.get(name, name)
            rec[key] = val
        if kind == "person":
            persons.append(rec)
        elif kind == "note":
            reports.append(rec)
    return persons, reports


def _coerce(rec: dict) -> dict:
    out = dict(rec)
    for f in _INT_FIELDS:
        if out.get(f) not in (None, ""):
            try:
                out[f] = int(out[f])
            except (ValueError, TypeError):
                out.pop(f, None)
    for f in _FLOAT_FIELDS:
        if out.get(f) not in (None, ""):
            try:
                out[f] = float(out[f])
            except (ValueError, TypeError):
                out.pop(f, None)
    return out


def _normalize(rec: dict, columns: set, reviewed_val: int, now: str,
               is_person: bool) -> dict:
    rec = _coerce(rec)
    out = {}
    for k, v in rec.items():
        key = {"createdAt": "created_at", "updatedAt": "updated_at"}.get(k, k)
        if key in columns:
            out[key] = v
    # Drop an invalid status (persons enforce a CHECK; keep reports clean too).
    if out.get("status") not in VALID_STATUSES:
        out.pop("status", None)
    base_prov = out.get("provenance")
    out["source"] = "pfif_import"
    if is_person:
        out["reviewed"] = reviewed_val
        out["provenance"] = (
            f"{base_prov + ' | ' if base_prov else ''}Imported via PFIF on {now}"
        )
    out["created_at"] = out.get("created_at") or now
    out["updated_at"] = out.get("updated_at") or now
    return out


def import_text(text: str, auto_approve: bool = False, dry_run: bool = False) -> dict:
    db.init_db()
    text = text.strip()
    if text.startswith("<"):
        persons, reports = _from_xml(text)
    else:
        data = json.loads(_strip_comment_lines(text))
        persons = data.get("records") or []
        reports = data.get("reports") or []

    reviewed_val = 1 if auto_approve else 0
    now = now_iso()
    p_saved = r_saved = skipped = 0

    with db.get_db() as conn:
        cur = conn.cursor()
        person_cols = {r[1] for r in cur.execute("PRAGMA table_info(persons)").fetchall()}
        report_cols = {r[1] for r in cur.execute("PRAGMA table_info(reports)").fetchall()}

        for p in persons:
            pid = p.get("id")
            if not pid:
                skipped += 1
                continue
            origin = p.get("origin_device")
            dup = cur.execute(
                "SELECT 1 FROM persons WHERE id = ? AND IFNULL(origin_device,'') = IFNULL(?,'')",
                (pid, origin),
            ).fetchone()
            if dup:
                skipped += 1
                continue
            rec = _normalize(p, person_cols, reviewed_val, now, is_person=True)
            rec["id"] = pid
            if not dry_run:
                cols = ", ".join(rec.keys())
                ph = ", ".join(f":{k}" for k in rec.keys())
                cur.execute(f"INSERT INTO persons ({cols}) VALUES ({ph})", rec)
            p_saved += 1

        for rep in reports:
            rid = rep.get("id")
            if not rid:
                skipped += 1
                continue
            origin = rep.get("origin_device")
            dup = cur.execute(
                "SELECT 1 FROM reports WHERE id = ? AND IFNULL(origin_device,'') = IFNULL(?,'')",
                (rid, origin),
            ).fetchone()
            if dup:
                skipped += 1
                continue
            rec = _normalize(rep, report_cols, reviewed_val, now, is_person=False)
            rec["id"] = rid
            if not dry_run:
                cols = ", ".join(rec.keys())
                ph = ", ".join(f":{k}" for k in rec.keys())
                cur.execute(f"INSERT INTO reports ({cols}) VALUES ({ph})", rec)
            r_saved += 1

        if not dry_run:
            conn.commit()

    return {"persons": p_saved, "reports": r_saved, "skipped": skipped}
