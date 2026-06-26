"""Routes for events, cities, and incidents."""

from typing import Optional

from fastapi import APIRouter, Query

from models import CityRecord, EventRecord, IncidentRecord
from modules import events

router = APIRouter()


@router.get("/events")
def list_events():
    return events.list_events()


@router.post("/events")
def upsert_event(event: EventRecord):
    return events.upsert_event(event)


@router.get("/cities")
def list_cities(event_id: Optional[str] = Query(None)):
    return events.list_cities(event_id)


@router.post("/cities")
def upsert_city(city: CityRecord):
    return events.upsert_city(city)


@router.get("/incidents")
def list_incidents(event_id: Optional[str] = Query(None)):
    return events.list_incidents(event_id)


@router.post("/incidents")
def upsert_incident(incident: IncidentRecord):
    return events.upsert_incident(incident)
