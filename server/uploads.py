"""Shared upload helpers (plan-30 §5.10).

A single home for the upload primitives that were copy-pasted across
``modules/photos.py``, ``modules/ocr_import.py``, ``routes/uploads.py`` and
``modules/flyer.py``:

  * :func:`validate_image_upload` — extension + content-type gate (415).
  * :func:`save_upload` — stream an ``UploadFile`` to disk under a size cap (413).
  * :func:`safe_path` — resolve a filename inside an upload dir, rejecting
    traversal.
  * :func:`url` — build the public ``/uploads/<name>`` URL for a stored file.

This module is intentionally dependency-light (stdlib + FastAPI only): it never
imports ``db``, ``ocr``, ``main`` or any other heavy server module, so any caller
can ``import uploads`` without risk of an import cycle. The upload directory is
always passed in as a parameter — never read from ``main`` here — so the test
suite's ``main.UPLOAD_DIR`` monkeypatch (resolved by the route layer at request
time) keeps working unchanged.
"""

import hashlib
from pathlib import Path
from typing import Optional, Union

from fastapi import HTTPException, UploadFile

# Upload guardrails (plan-07 §12.1): only accept images, and cap the size so a
# huge upload can't exhaust disk. Canonical copy lives here; modules/ocr_import.py
# and modules/photos.py import these names from this module.
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_image_upload(file: UploadFile) -> str:
    """Reject non-image uploads up front and return the file's extension.

    Validates by extension and, when present, by the declared content type so an
    upload route can't be used as an arbitrary file drop. Raises
    ``HTTPException(415)`` for a bad extension or content type. Returns the
    original extension (including the leading dot, e.g. ``".jpg"``) so callers can
    build a stored filename / suffix from it.
    """
    ext = Path(file.filename or "image.jpg").suffix
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
    return ext


def save_upload(file: UploadFile, dest: Path, max_bytes: int = MAX_UPLOAD_BYTES) -> str:
    """Stream an ``UploadFile`` to ``dest`` while enforcing ``max_bytes``.

    Writes the upload in chunks, hashing as it goes, and returns the SHA-256 hex
    digest of the bytes written (callers that need a content-hash filename use it;
    callers that don't can ignore it). If the stream exceeds ``max_bytes`` the
    partial file is unlinked and ``HTTPException(413)`` is raised. The underlying
    upload stream is always closed.
    """
    dest = Path(dest)
    hasher = hashlib.sha256()
    written = 0
    try:
        with open(dest, "wb") as f:
            for chunk in file.file:
                written += len(chunk)
                if written > max_bytes:
                    f.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Image exceeds the {max_bytes // (1024 * 1024)} MB limit.",
                    )
                hasher.update(chunk)
                f.write(chunk)
    finally:
        file.file.close()
    return hasher.hexdigest()


def safe_path(upload_dir: Union[str, Path], filename: str) -> Optional[Path]:
    """Resolve ``filename`` inside ``upload_dir``, rejecting path traversal.

    Returns the resolved :class:`~pathlib.Path` when it stays within
    ``upload_dir``; returns ``None`` when the candidate escapes the directory.
    Existence is NOT checked here — the caller decides what to do (404, fall back
    to a placeholder, …) and whether the path must be a file.
    """
    base = Path(upload_dir).resolve()
    candidate = (base / filename).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def url(filename: str) -> str:
    """Build the public URL for a stored upload (served via GET /uploads/...)."""
    return f"/uploads/{filename}"
