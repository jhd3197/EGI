"""Routes for user preferences, subscriptions & alerts (plan-24).

All preference endpoints are scoped to the authenticated user (``require_user``):
preferences are inherently per-account and there is no operator/dev bypass here.
The category catalogue (``GET /preferences/categories``) is public so the UI can
render the Settings grid and its i18n labels even before a preference is set.
"""

from fastapi import APIRouter, Depends

from auth import require_user
from models import (
    CONTENT_CATEGORIES,
    DEFAULT_NOTIFY_CATEGORIES,
    PreferencesUpdate,
)
from modules import preferences

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


@router.put("")
def update_preferences(patch: PreferencesUpdate, user: dict = Depends(require_user)):
    return preferences.set_preferences(user["id"], patch)
