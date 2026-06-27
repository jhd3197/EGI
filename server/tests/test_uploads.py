# Photo/upload privacy (plan-07 Phase 4). TEST DATA — NOT REAL.
# Uploads are never publicly served: the /uploads route is operator-gated and
# disabled unless ENABLE_PHOTOS=true. EXIF is stripped on upload.

import io

from PIL import Image

import ocr


def _write_image_with_exif(path):
    img = Image.new("RGB", (8, 8), color=(120, 30, 30))
    # Attach a fake GPS/EXIF blob so we can prove it's gone after stripping.
    exif = img.getexif()
    exif[0x010E] = "secret location note"  # ImageDescription
    img.save(path, exif=exif)


def test_uploads_disabled_returns_403(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "false")
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    res = client.get("/uploads/anything.jpg")
    assert res.status_code == 403


def test_uploads_requires_operator_when_enabled(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.setenv("OPERATOR_TOKENS", "photo-token-1")
    # Place a real file in the (monkeypatched) upload dir.
    import main
    (main.UPLOAD_DIR / "p.jpg").write_bytes(b"img")

    # No token -> 401 (not publicly accessible).
    assert client.get("/uploads/p.jpg").status_code == 401
    # With token -> 200.
    ok = client.get("/uploads/p.jpg", headers={"Authorization": "Bearer photo-token-1"})
    assert ok.status_code == 200


def test_uploads_blocks_path_traversal(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)
    res = client.get("/uploads/..%2F..%2Fsecret.txt")
    assert res.status_code == 404


def test_strip_exif_removes_metadata(tmp_path):
    p = tmp_path / "photo.jpg"
    _write_image_with_exif(p)
    assert dict(Image.open(p).getexif())  # EXIF present before
    assert ocr.strip_exif(p) is True
    assert not dict(Image.open(p).getexif())  # EXIF gone after


def test_strip_exif_noop_on_non_image(tmp_path):
    p = tmp_path / "not.jpg"
    p.write_bytes(b"definitely-not-an-image")
    assert ocr.strip_exif(p) is False  # best-effort, no raise


def test_photo_url_redacted_from_public_search(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "false")
    client.post("/sync", json={"records": [{
        "id": "egi-photo-1", "name": "Con foto", "status": "missing",
        "photo_url": "/uploads/secret.jpg", "image_path": "/uploads/secret.jpg",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    }]})
    rec = next(r for r in client.get("/persons").json()["records"] if r["id"] == "egi-photo-1")
    assert rec["photo_url"] is None
    assert rec["image_path"] is None
