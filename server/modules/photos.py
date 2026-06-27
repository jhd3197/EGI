"""Photo business logic for person records (plan-10 Phase 2).

Photos of people in a crisis are high-risk, so this module is deliberately
privacy-conservative:

  * The uploader's original filename is NEVER stored — the on-disk name is a
    content hash (``<sha256>.jpg``), and a separate ``<hash>_thumb.jpg`` holds a
    small thumbnail.
  * GPS / capture-time EXIF is lifted into structured ``lat``/``lon``/``taken_at``
    columns *before* the image is re-encoded, and the stored file is then
    EXIF-stripped so the served bytes carry no metadata.
  * Files live in the upload dir and are served ONLY through the operator-gated,
    ``ENABLE_PHOTOS``-guarded ``GET /uploads/{filename}`` route (routes/uploads.py).

The upload directory is injected by the route layer (read from ``main`` at
request time) so the test suite's ``main.UPLOAD_DIR`` monkeypatch keeps working,
mirroring modules/ocr_import.py.
"""

import hashlib
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from PIL import Image

import db
import ocr
from models import now_iso
from modules import audit
from modules.ocr_import import ALLOWED_IMAGE_EXTS, MAX_UPLOAD_BYTES
from security import photos_enabled

# Largest dimension of the stored main image; only downscaled, never upscaled.
MAX_IMAGE_DIM = 1200
# Thumbnail bounding box (fit within, preserving aspect ratio).
THUMBNAIL_SIZE = (300, 300)


def _person_exists(person_id: str) -> bool:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM persons WHERE id = ?", (person_id,)
        ).fetchone()
        return row is not None


def _photo_to_dict(row) -> dict:
    """Map a photos row to the API shape, deriving served URLs from the hashes."""
    d = db.row_to_dict(row)
    return {
        "id": d["id"],
        "person_id": d["person_id"],
        "url": f"/uploads/{d['filename_hash']}",
        "thumbnail_url": (
            f"/uploads/{d['thumbnail_hash']}" if d.get("thumbnail_hash") else None
        ),
        "width": d.get("width"),
        "height": d.get("height"),
        "lat": d.get("lat"),
        "lon": d.get("lon"),
        "taken_at": d.get("taken_at"),
        "created_at": d.get("created_at"),
    }


def add_photo(
    person_id: str,
    file: UploadFile,
    upload_dir: Path,
    uploader_id: Optional[str] = None,
) -> dict:
    """Attach a photo to a person: validate, hash, EXIF-strip, resize, thumbnail.

    Returns the new photo record (with ``url``/``thumbnail_url``). Raises 404 if
    the person does not exist, 415 for non-image uploads, and 413 when the file
    exceeds ``MAX_UPLOAD_BYTES``.
    """
    if not _person_exists(person_id):
        raise HTTPException(status_code=404, detail="Person not found")

    ext = Path(file.filename or "image.jpg").suffix
    # Reject non-image uploads up front (by extension and declared content type)
    # so the route can't be used as an arbitrary file drop.
    if ext.lower() not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Upload an image.",
        )
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type '{file.content_type}'. Upload an image.",
        )

    # Stream to a temp file while enforcing the size cap, hashing as we go. The
    # original filename is never used for the stored name.
    hasher = hashlib.sha256()
    written = 0
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=ext, dir=str(upload_dir))
    tmp_path = Path(tmp_name)
    try:
        with open(tmp_fd, "wb") as f:
            for chunk in file.file:
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
                    )
                hasher.update(chunk)
                f.write(chunk)
    except HTTPException:
        tmp_path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    digest = hasher.hexdigest()
    filename_hash = f"{digest}.jpg"
    thumbnail_hash = f"{digest}_thumb.jpg"
    main_dest = upload_dir / filename_hash
    thumb_dest = upload_dir / thumbnail_hash

    # Lift GPS / capture time from EXIF BEFORE we re-encode (which drops it).
    lat = lon = None
    gps = ocr.extract_gps(tmp_path)
    if gps:
        lat, lon = gps
    taken_at = ocr.extract_taken_at(tmp_path)

    try:
        with Image.open(tmp_path) as img:
            img = img.convert("RGB")
            # Only downscale: largest dimension capped at MAX_IMAGE_DIM.
            w, h = img.size
            longest = max(w, h)
            if longest > MAX_IMAGE_DIM:
                scale = MAX_IMAGE_DIM / float(longest)
                img = img.resize(
                    (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS
                )
            img.save(main_dest, format="JPEG", quality=85)
            out_w, out_h = img.size

            # Thumbnail: fit within THUMBNAIL_SIZE, preserving aspect ratio.
            thumb = img.copy()
            thumb.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
            thumb.save(thumb_dest, format="JPEG", quality=80)
    except HTTPException:
        raise
    except Exception as exc:
        main_dest.unlink(missing_ok=True)
        thumb_dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Invalid image: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    # Re-encoding already drops EXIF, but strip again defensively.
    ocr.strip_exif(main_dest)

    photo_id = f"egi-photo-{uuid.uuid4().hex[:8]}"
    now = now_iso()
    content_type = "image/jpeg"

    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO photos
            (id, person_id, uploader_id, filename_hash, thumbnail_hash,
             width, height, content_type, lat, lon, taken_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                photo_id, person_id, uploader_id, filename_hash, thumbnail_hash,
                out_w, out_h, content_type, lat, lon, taken_at, now,
            ),
        )
        conn.commit()

    audit.log_history(
        person_id, "photo_add", actor=uploader_id or "system", source="photo"
    )

    return {
        "id": photo_id,
        "person_id": person_id,
        "url": f"/uploads/{filename_hash}",
        "thumbnail_url": f"/uploads/{thumbnail_hash}",
        "width": out_w,
        "height": out_h,
        "lat": lat,
        "lon": lon,
        "taken_at": taken_at,
        "created_at": now,
    }


def list_photos(person_id: str) -> dict:
    """List a person's photos, newest first.

    When photos are globally disabled (``ENABLE_PHOTOS`` unset/false) this
    returns an empty list and does NOT disclose that photos exist.
    """
    if not photos_enabled():
        return {"records": []}
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM photos WHERE person_id = ? ORDER BY created_at DESC, id DESC",
            (person_id,),
        ).fetchall()
    return {"records": [_photo_to_dict(r) for r in rows]}


def delete_photo(photo_id: str, upload_dir: Path) -> dict:
    """Delete a photo row and best-effort unlink both files. 404 if not found."""
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM photos WHERE id = ?", (photo_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        data = db.row_to_dict(row)
        conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        conn.commit()

    # Best-effort file cleanup; a missing file must not fail the delete.
    for name in (data.get("filename_hash"), data.get("thumbnail_hash")):
        if name:
            try:
                (upload_dir / name).unlink(missing_ok=True)
            except Exception:
                pass

    audit.log_history(
        data["person_id"], "photo_delete", actor="system", source="photo"
    )
    return {"ok": True, "id": photo_id}
