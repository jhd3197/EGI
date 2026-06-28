"""Federation routes (plan-12 §4): thin HTTP adapters over modules.federation.

Trusted peers are operator-managed server-local configuration, so the whole
router is gated at operator level (consistent with the webhooks router). Request
bodies are local Pydantic models (precedent: NormalizeRequest in
routes/imports.py) to avoid editing models.py.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import require_operator
from modules import federation

router = APIRouter()


class PeerCreate(BaseModel):
    name: str
    base_url: str
    public_key: Optional[str] = None
    token: Optional[str] = None


class PeerUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    public_key: Optional[str] = None
    token: Optional[str] = None
    active: Optional[int] = None


@router.post("/federation/peers")
def create_peer(req: PeerCreate, principal: str = Depends(require_operator)):
    return federation.add_peer(
        name=req.name, base_url=req.base_url,
        public_key=req.public_key, token=req.token,
    )


@router.get("/federation/peers")
def list_peers(principal: str = Depends(require_operator)):
    return federation.list_peers()


@router.get("/federation/peers/{peer_id}")
def get_peer(peer_id: str, principal: str = Depends(require_operator)):
    return federation.get_peer(peer_id)


@router.patch("/federation/peers/{peer_id}")
def update_peer(
    peer_id: str, req: PeerUpdate, principal: str = Depends(require_operator)
):
    return federation.update_peer(peer_id, **req.model_dump(exclude_unset=True))


@router.delete("/federation/peers/{peer_id}")
def delete_peer(peer_id: str, principal: str = Depends(require_operator)):
    return federation.remove_peer(peer_id)


@router.post("/federation/peers/{peer_id}/pull")
def pull_peer(peer_id: str, principal: str = Depends(require_operator)):
    return federation.pull_from_peer(peer_id)


@router.post("/federation/peers/{peer_id}/push")
def push_peer(peer_id: str, principal: str = Depends(require_operator)):
    return federation.push_to_peer(peer_id)


@router.post("/federation/peers/{peer_id}/sync")
def sync_peer(peer_id: str, principal: str = Depends(require_operator)):
    return federation.sync_peer(peer_id)
