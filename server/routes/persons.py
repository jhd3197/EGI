"""Routes for person search/get and per-person reports."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from models import ReportRecord
from modules import persons, reports
from ratelimit import rate_limit

router = APIRouter()


@router.get("/persons")
def search_persons(
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    disaster_id: Optional[str] = Query(None),
    cedula: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
):
    return persons.search_persons(
        q=q, status=status, location=location, disaster_id=disaster_id,
        cedula=cedula, since=since, limit=limit, cursor=cursor,
    )


@router.get("/persons/{person_id}")
def get_person(person_id: str):
    return persons.get_person(person_id)


@router.get("/persons/{person_id}/reports")
def list_person_reports(person_id: str):
    return reports.list_person_reports(person_id)


@router.post("/persons/{person_id}/reports", dependencies=[Depends(rate_limit)])
def create_person_report(person_id: str, report: ReportRecord):
    return reports.create_person_report(person_id, report)
