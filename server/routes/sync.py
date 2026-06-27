"""Routes for the sync contract: POST /sync (upload) and GET /sync (download)."""

from typing import Optional

from fastapi import APIRouter, Depends

from models import SyncPayload
from modules import sync
from ratelimit import rate_limit

router = APIRouter()


@router.post("/sync", dependencies=[Depends(rate_limit)])
def sync_upload(payload: SyncPayload):
    return sync.sync_upload(payload)


@router.get("/sync")
def sync_download(since: Optional[str] = None):
    return sync.sync_download(since)
