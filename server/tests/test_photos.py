# Per-person photo upload/list/delete (plan-10 Phase 2). TEST DATA — NOT REAL.
# Crisis photos are high-risk: uploads are operator-gated, hidden behind
# ENABLE_PHOTOS, stored under a content hash (never the original filename),
# resized, and EXIF-stripped. GPS EXIF is lifted into lat/lon before stripping.

from PIL import Image

import main
import ocr
from factories import sync_person
from images import jpeg_with_gps_bytes as _jpeg_with_gps_bytes
from images import png_bytes as _png_bytes

# The router is wired into main.py by the orchestrator; include it here too so
# the routes exist under the TestClient. Guard against a double include if the
# orchestrator has already added it.
from routes import photos as photos_routes  # noqa: E402

if not any(
    getattr(r, "path", None) == "/persons/{person_id}/photos"
    for r in main.app.router.routes
):
    main.app.include_router(photos_routes.router)
    # The SPA catch-all (GET /{path:path}) must stay last or it shadows our GET
    # routes. include_router appends after it, so move it back to the end.
    routes = main.app.router.routes
    catchall = [r for r in routes if getattr(r, "path", None) == "/{path:path}"]
    for r in catchall:
        routes.remove(r)
        routes.append(r)


# --- helpers ----------------------------------------------------------------

def _seed_person(client, person_id="egi-p-1"):
    return sync_person(client, id=person_id, name="Persona Falsa")["id"]


def _op_headers():
    return {"Authorization": "Bearer photo-token-1"}


# --- auth / feature-flag gating --------------------------------------------

def test_upload_requires_operator_when_enabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    pid = _seed_person(client)

    files = {"file": ("photo.png", _png_bytes(), "image/png")}
    # No token -> 401.
    assert client.post(f"/persons/{pid}/photos", files=files).status_code == 401

    files = {"file": ("photo.png", _png_bytes(), "image/png")}
    res = client.post(f"/persons/{pid}/photos", files=files, headers=_op_headers())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["person_id"] == pid
    assert body["url"].startswith("/uploads/")
    assert body["thumbnail_url"].startswith("/uploads/")


def test_upload_403_when_photos_disabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "false")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    pid = _seed_person(client)
    files = {"file": ("photo.png", _png_bytes(), "image/png")}
    res = client.post(f"/persons/{pid}/photos", files=files, headers=_op_headers())
    assert res.status_code == 403


def test_upload_unknown_person_404(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    files = {"file": ("photo.png", _png_bytes(), "image/png")}
    res = client.post("/persons/does-not-exist/photos", files=files, headers=_op_headers())
    assert res.status_code == 404


def test_upload_rejects_non_image(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    pid = _seed_person(client)
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    res = client.post(f"/persons/{pid}/photos", files=files, headers=_op_headers())
    assert res.status_code == 415


# --- image processing -------------------------------------------------------

def test_upload_downscales_large_image(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    pid = _seed_person(client)
    big = _png_bytes(size=(2000, 1000))
    files = {"file": ("big.png", big, "image/png")}
    res = client.post(f"/persons/{pid}/photos", files=files, headers=_op_headers())
    assert res.status_code == 200, res.text
    body = res.json()
    assert max(body["width"], body["height"]) <= 1200
    # 2000x1000 -> 1200x600.
    assert body["width"] == 1200 and body["height"] == 600

    # Stored file on disk reflects the downscale and carries no EXIF.
    stored = main.UPLOAD_DIR / body["url"].split("/")[-1]
    assert stored.is_file()
    with Image.open(stored) as im:
        assert max(im.size) <= 1200
        assert not dict(im.getexif())  # EXIF stripped


def test_upload_extracts_gps_from_exif(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    pid = _seed_person(client)
    files = {"file": ("gps.jpg", _jpeg_with_gps_bytes(), "image/jpeg")}
    res = client.post(f"/persons/{pid}/photos", files=files, headers=_op_headers())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["lat"] is not None and body["lon"] is not None
    # ~40.4461 N, ~-79.9821 W (fake).
    assert abs(body["lat"] - 40.4461) < 0.01
    assert abs(body["lon"] - (-79.9821)) < 0.01
    assert body["taken_at"] == "2026-01-02 03:04:05"

    # The stored image itself must not retain the GPS EXIF.
    stored = main.UPLOAD_DIR / body["url"].split("/")[-1]
    assert ocr.extract_gps(stored) is None


def test_upload_strips_exif_on_stored_file(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    pid = _seed_person(client)
    files = {"file": ("gps.jpg", _jpeg_with_gps_bytes(), "image/jpeg")}
    res = client.post(f"/persons/{pid}/photos", files=files, headers=_op_headers())
    stored = main.UPLOAD_DIR / res.json()["url"].split("/")[-1]
    with Image.open(stored) as im:
        assert not dict(im.getexif())


# --- list / delete ----------------------------------------------------------

def test_list_and_delete(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    pid = _seed_person(client)
    files = {"file": ("photo.png", _png_bytes(), "image/png")}
    up = client.post(f"/persons/{pid}/photos", files=files, headers=_op_headers())
    photo_id = up.json()["id"]
    main_file = main.UPLOAD_DIR / up.json()["url"].split("/")[-1]
    thumb_file = main.UPLOAD_DIR / up.json()["thumbnail_url"].split("/")[-1]
    assert main_file.is_file() and thumb_file.is_file()

    listing = client.get(f"/persons/{pid}/photos")
    assert listing.status_code == 200
    ids = [r["id"] for r in listing.json()["records"]]
    assert photo_id in ids

    # Delete requires operator.
    assert client.delete(f"/photos/{photo_id}").status_code == 401
    res = client.delete(f"/photos/{photo_id}", headers=_op_headers())
    assert res.status_code == 200
    # Files cleaned up + row gone.
    assert not main_file.exists() and not thumb_file.exists()
    assert photo_id not in [r["id"] for r in client.get(f"/persons/{pid}/photos").json()["records"]]
    # Deleting again -> 404.
    assert client.delete(f"/photos/{photo_id}", headers=_op_headers()).status_code == 404


def test_list_empty_when_photos_disabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    pid = _seed_person(client)
    files = {"file": ("photo.png", _png_bytes(), "image/png")}
    client.post(f"/persons/{pid}/photos", files=files, headers=_op_headers())
    # Now disable: listing discloses nothing.
    monkeypatch.setenv("ENABLE_PHOTOS", "false")
    assert client.get(f"/persons/{pid}/photos").json()["records"] == []
