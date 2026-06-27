"""Routes for per-person photo upload / listing / deletion (plan-10 Phase 2).

Thin HTTP adapter over ``modules.photos`` (mirrors routes/imports.py +
routes/uploads.py). Photos are high-risk crisis data, so every mutating route is
operator-gated and the whole feature is hidden behind ``ENABLE_PHOTOS``:

  * Uploads/deletes require operator auth and 403 when photos are disabled.
  * Listing is public (like ``GET /persons``) but the module returns nothing
    when photos are disabled, so disabled deployments disclose no photo data.

The upload dir is read from ``main`` at request time so the suite's
``main.UPLOAD_DIR`` monkeypatch keeps working (same pattern as routes/imports.py).
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth import require_operator
from modules import photos
from ratelimit import rate_limit
from security import photos_enabled

router = APIRouter()


@router.post("/persons/{person_id}/photos", dependencies=[Depends(rate_limit)])
def upload_photo(
    person_id: str,
    file: UploadFile = File(...),
    operator: str = Depends(require_operator),
):
    if not photos_enabled():
        raise HTTPException(status_code=403, detail="Photos are disabled")
    import main  # late import: honor a monkeypatched UPLOAD_DIR at call time

    return photos.add_photo(
        person_id=person_id,
        file=file,
        upload_dir=main.UPLOAD_DIR,
        uploader_id=operator,
    )


@router.get("/persons/{person_id}/photos")
def list_photos(person_id: str):
    # Public read like GET /persons; the module gates on photos_enabled() and
    # returns an empty list when photos are disabled.
    return photos.list_photos(person_id)


@router.delete("/photos/{photo_id}")
def delete_photo(photo_id: str, operator: str = Depends(require_operator)):
    if not photos_enabled():
        raise HTTPException(status_code=403, detail="Photos are disabled")
    import main  # late import: honor a monkeypatched UPLOAD_DIR at call time

    return photos.delete_photo(photo_id, upload_dir=main.UPLOAD_DIR)
