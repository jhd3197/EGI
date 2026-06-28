"""Access-controlled photo serving (plan-07 §7).

Photos of people in a crisis are high-risk, so they are NOT served from a public
static mount. Instead this operator-gated route streams a file from the upload
directory only when:
  * photos are enabled (``ENABLE_PHOTOS=true``), and
  * the caller passes operator auth (``Authorization: Bearer <token>``).

The upload dir is read from ``main`` at request time so the test suite's
``main.UPLOAD_DIR`` monkeypatch keeps working (same pattern as the OCR route).
Path traversal is blocked by resolving the candidate and confirming it stays
inside the upload directory.
"""

import uploads
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth import require_operator
from security import photos_enabled

router = APIRouter()


@router.get("/uploads/{filename:path}")
def serve_upload(filename: str, operator: str = Depends(require_operator)):
    if not photos_enabled():
        # Photos disabled: never serve, even to an operator.
        raise HTTPException(status_code=403, detail="Photos are disabled")

    import main  # late import: honor a monkeypatched UPLOAD_DIR at call time

    # Reject path traversal: the resolved path must stay within upload_dir.
    candidate = uploads.safe_path(main.UPLOAD_DIR, filename)
    if candidate is None or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(candidate)
