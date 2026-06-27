# Voice transcript persistence + transcribe route (plan-14 §6). TEST DATA — NOT REAL.

from modules import voice


def test_save_and_list_transcript(client):
    voice.save_transcript(
        "estoy en el refugio norte", person_id="egi-test-voice-1",
        confidence=0.82, language="es",
    )
    records = voice.list_transcripts("egi-test-voice-1")["records"]
    assert len(records) == 1
    assert records[0]["transcript"] == "estoy en el refugio norte"
    assert records[0]["confidence"] == 0.82


def test_available_false_in_test_env(client):
    assert voice.available() is False


def test_transcribe_route_503_without_backend(client):
    res = client.post(
        "/voice/transcribe",
        files={"file": ("a.ogg", b"x", "audio/ogg")},
    )
    assert res.status_code == 503
