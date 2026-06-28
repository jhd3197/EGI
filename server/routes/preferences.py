"""Routes for user preferences, subscriptions & alerts (plan-24).

All preference endpoints are scoped to the authenticated user (``require_user``):
preferences are inherently per-account and there is no operator/dev bypass here.
The category catalogue (``GET /preferences/categories``) is public so the UI can
render the Settings grid and its i18n labels even before a preference is set.
"""

from fastapi import APIRouter, Depends

from auth import require_user, user_principal
from models import (
    CONTENT_CATEGORIES,
    DEFAULT_NOTIFY_CATEGORIES,
    PreferencesUpdate,
)
from modules import audit, notifications, preferences
from ratelimit import rate_limit

router = APIRouter(prefix="/preferences")


@router.get("/categories")
def categories():
    """The catalogue of content categories + their notify-by-default policy."""
    return {
        "categories": [
            {
                "key": c,
                "notify_default": c in DEFAULT_NOTIFY_CATEGORIES,
            }
            for c in sorted(CONTENT_CATEGORIES)
        ]
    }


@router.get("")
def get_preferences(user: dict = Depends(require_user)):
    return preferences.get_preferences(user["id"])


@router.put("", dependencies=[Depends(rate_limit)])
def update_preferences(patch: PreferencesUpdate, user: dict = Depends(require_user)):
    """Patch the caller's preferences. Rate-limited + audited (plan-24 Phase 7).

    The preference layer can never silence a life-safety alert: own-record
    matches and ``life_safety`` broadcasts bypass these toggles in the
    notification gate, so saving any combination here is safe.
    """
    result = preferences.set_preferences(user["id"], patch)
    changed = [c.category for c in (patch.categories or [])]
    if patch.settings is not None:
        changed.append("settings")
    audit.log_action(
        user_principal(user), "preferences_update", "preferences", user["id"],
        detail=f"changed={','.join(changed) or 'none'} skipped={result.get('skipped', 0)}",
    )
    return result


@router.post("/notify-test")
def notify_test(user: dict = Depends(require_user)):
    """Send a test push to the caller's own devices so they can verify delivery."""
    return notifications.send_test(user["id"])
