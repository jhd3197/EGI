# Printable missing-person PDF flyer (plan-12 Phase 2). TEST DATA — NOT REAL.
# The flyer leaves the system, so it must respect ENABLE_PHOTOS (no crisis photo
# embedded when disabled) and always carry the privacy disclaimer.

from PIL import Image

import db
from assertions import assert_is_pdf
from factories import sync_person
from models import now_iso


def _seed_person(client, person_id="egi-flyer-1", **fields):
    record = {
        "name": "Persona Falsa",
        "status": "missing",
        "age": 34,
        "sex": "F",
        "last_seen_date": "2026-06-01",
        "last_known_location": "Plaza Central, Ciudad Falsa",
        "contact": "+58 412 555 0100",
    }
    record.update(fields)
    return sync_person(client, id=person_id, **record)["id"]


def test_flyer_without_photo_returns_pdf(client):
    pid = _seed_person(client)
    res = client.get(f"/persons/{pid}/flyer.pdf")
    assert_is_pdf(res)
    assert res.headers["content-type"] == "application/pdf"
    assert "inline" in res.headers["content-disposition"]


def test_flyer_unknown_person_404(client):
    res = client.get("/persons/does-not-exist/flyer.pdf")
    assert res.status_code == 404


def test_flyer_all_langs(client):
    pid = _seed_person(client)
    for lang in ("es", "en", "pt"):
        res = client.get(f"/persons/{pid}/flyer.pdf", params={"lang": lang})
        assert_is_pdf(res)


def test_flyer_no_contact_still_renders(client):
    pid = _seed_person(client, person_id="egi-flyer-nc", contact=None)
    res = client.get(f"/persons/{pid}/flyer.pdf")
    assert_is_pdf(res)


def test_flyer_embeds_photo_when_enabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_PHOTOS", "true")
    # Drop a real image into the upload dir and point the record at it.
    import main

    img_name = "flyer-photo.jpg"
    Image.new("RGB", (80, 100), (40, 60, 80)).save(main.UPLOAD_DIR / img_name)
    pid = "egi-flyer-photo"
    with db.get_db() as conn:
        now = now_iso()
        conn.execute(
            "INSERT INTO persons (id, name, status, image_path, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, "Persona Con Foto", "missing", f"/uploads/{img_name}", now, now),
        )
        conn.commit()

    res = client.get(f"/persons/{pid}/flyer.pdf")
    assert_is_pdf(res)


def test_flyer_no_photo_when_disabled(client, monkeypatch):
    # Even with an image_path set, photos disabled => flyer renders (placeholder),
    # never embedding the crisis photo.
    monkeypatch.setenv("ENABLE_PHOTOS", "false")
    import main

    img_name = "flyer-photo-2.jpg"
    Image.new("RGB", (80, 100), (10, 10, 10)).save(main.UPLOAD_DIR / img_name)
    pid = "egi-flyer-photo-off"
    with db.get_db() as conn:
        now = now_iso()
        conn.execute(
            "INSERT INTO persons (id, name, status, image_path, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, "Persona Oculta", "missing", f"/uploads/{img_name}", now, now),
        )
        conn.commit()

    res = client.get(f"/persons/{pid}/flyer.pdf")
    assert_is_pdf(res)
