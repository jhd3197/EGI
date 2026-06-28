"""HTTP adapters for remote-moderator onboarding (plan-25 Phase 4).

Onboarding is bound to a real user account. The queue is what that moderator
should review. A coordinator (operator) can see the roster + the digest numbers.
"""

from fastapi import APIRouter, Depends

from auth import require_operator, require_user
from models import ModeratorSignup
from modules import audit, moderators

router = APIRouter(prefix="/moderators")


@router.post("/signup")
def signup(body: ModeratorSignup, user: dict = Depends(require_user)):
    """Sign up as a moderator (invite-gated deployments pass invite_token)."""
    mod = moderators.signup(
        user["id"],
        display_name=body.display_name or user.get("name"),
        languages=body.languages,
        regions=body.regions,
    )
    audit.log_action(
        f"user:{user['id']}", "moderator_signup", "moderator", user["id"],
        detail=f"invite={bool(body.invite_token)}",
    )
    return mod


@router.get("/me")
def me(user: dict = Depends(require_user)):
    mod = moderators.get(user["id"])
    return mod or {"moderator": False}


@router.post("/me/trained")
def mark_trained(user: dict = Depends(require_user)):
    """Flip the trained flag after the volunteer reviews the training example."""
    return moderators.mark_trained(user["id"])


@router.get("/me/queue")
def my_queue(limit: int = 50, user: dict = Depends(require_user)):
    return moderators.queue(user["id"], limit=limit)


@router.get("")
def roster(operator: str = Depends(require_operator)):
    """Operator/coordinator: the moderator roster."""
    return {"moderators": moderators.list_moderators(active_only=True)}


@router.get("/digest")
def digest(operator: str = Depends(require_operator)):
    """Queue-size snapshot used for the moderator digest."""
    return moderators.digest()
