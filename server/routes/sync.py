"""Routes for the sync contract: POST /sync (upload) and GET /sync (download)."""

from typing import Optional

from fastapi import APIRouter, Depends

from models import OperationSyncPayload, SyncPayload
from modules import sync
from ratelimit import rate_limit

router = APIRouter()


@router.post("/sync", dependencies=[Depends(rate_limit)])
def sync_upload(payload: SyncPayload):
    return sync.sync_upload(payload)


@router.get("/sync")
def sync_download(since: Optional[str] = None):
    return sync.sync_download(since)


@router.get("/sync/operations")
def sync_operations_download(since: Optional[str] = None):
    return sync.operations_download(since)


@router.post("/sync/operations", dependencies=[Depends(rate_limit)])
def sync_operations_upload(payload: OperationSyncPayload):
    return sync.operations_upload(payload)
