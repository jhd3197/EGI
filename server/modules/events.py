"""Event / city / incident logic (PFIF-aligned domain objects)."""

import uuid
from typing import Optional

import db
from models import CityRecord, EventRecord, IncidentRecord, now_iso


def list_events() -> dict:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY created_at DESC").fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def upsert_event(event: EventRecord) -> dict:
    now = now_iso()
    event_id = event.id or f"egi-event-{uuid.uuid4().hex[:8]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO events
            (id, name, region, type, tag, date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id, event.name, event.region, event.type, event.tag,
                event.date, event.status, event.createdAt or now,
                event.updatedAt or now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return db.row_to_dict(row)


def list_cities(event_id: Optional[str] = None) -> dict:
    sql = "SELECT * FROM cities WHERE 1=1"
    params: list = []
    if event_id:
        sql += " AND event_id = ?"
        params.append(event_id)
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def upsert_city(city: CityRecord) -> dict:
    now = now_iso()
    city_id = city.id or f"egi-city-{uuid.uuid4().hex[:8]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO cities
            (id, event_id, name, region, lat, lon, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                city_id, city.event_id, city.name, city.region, city.lat,
                city.lon, city.createdAt or now, city.updatedAt or now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cities WHERE id = ?", (city_id,)).fetchone()
        return db.row_to_dict(row)


def list_incidents(event_id: Optional[str] = None) -> dict:
    sql = "SELECT * FROM incidents WHERE 1=1"
    params: list = []
    if event_id:
        sql += " AND event_id = ?"
        params.append(event_id)
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def upsert_incident(incident: IncidentRecord) -> dict:
    now = now_iso()
    incident_id = incident.id or f"egi-incident-{uuid.uuid4().hex[:8]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO incidents
            (id, event_id, kind, title, description, lat, lon, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id, incident.event_id, incident.kind, incident.title,
                incident.description, incident.lat, incident.lon,
                incident.createdAt or now, incident.updatedAt or now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return db.row_to_dict(row)
