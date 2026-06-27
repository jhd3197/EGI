# Chatbot conversation engine (plan-14 §4/§5). TEST DATA — NOT REAL.

from modules import chatbot

USER = "+584140000001"


def _report_flow(user=USER):
    """Drive a full report conversation and return the final draft."""
    chatbot.handle_message("whatsapp", user, text="reportar")
    chatbot.handle_message("whatsapp", user, text="Pedro Pérez")
    chatbot.handle_message("whatsapp", user, text="V-12345678")
    chatbot.handle_message("whatsapp", user, text="Refugio Norte")
    return chatbot.handle_message("whatsapp", user, text="desaparecido")


def test_report_flow_creates_full_draft(client):
    res = _report_flow()
    draft = res["draft"]
    assert res["ended"] is True
    assert draft["name"] == "Pedro Pérez"
    assert draft["cedula"] == "V-12345678"
    assert draft["last_known_location"] == "Refugio Norte"
    assert draft["status"] == "missing"
    assert draft["source"] == "whatsapp"
    assert draft["reviewed"] == 0


def test_safe_flow_creates_safe_draft(client):
    chatbot.handle_message("whatsapp", "+584140000002", text="estoy bien")
    res = chatbot.handle_message("whatsapp", "+584140000002", text="Ana Gómez")
    # safe flow asks cédula next; answer to finish.
    res = chatbot.handle_message("whatsapp", "+584140000002", text="no")
    draft = res["draft"]
    assert res["ended"] is True
    assert draft["name"] == "Ana Gómez"
    assert draft["status"] == "safe"
    assert draft["source"] == "whatsapp"
    assert draft["reviewed"] == 0


def test_search_empty_then_found_after_approve(client):
    # Empty verified registry → not-found copy.
    chatbot.handle_message("whatsapp", "+584140000003", text="buscar")
    res = chatbot.handle_message("whatsapp", "+584140000003", text="Pedro")
    assert "No encontramos" in res["reply"]

    # Create + approve a report so it becomes a trusted, searchable record.
    draft = _report_flow("+584140000099")["draft"]
    client.post(f"/moderation/{draft['id']}/approve")

    chatbot.handle_message("whatsapp", "+584140000004", text="buscar")
    res = chatbot.handle_message("whatsapp", "+584140000004", text="Pedro")
    assert "Pedro Pérez" in res["reply"]


def test_optout_ends_session(client):
    chatbot.handle_message("whatsapp", "+584140000005", text="reportar")
    res = chatbot.handle_message("whatsapp", "+584140000005", text="detener")
    assert res["ended"] is True
    # Session was deleted: a follow-up starts at the welcome menu again.
    res = chatbot.handle_message("whatsapp", "+584140000005", text="hola")
    assert res["quick_replies"]  # menu replies present → fresh start


def test_draft_hidden_until_approved(client):
    draft = _report_flow("+584140000006")["draft"]
    pid = draft["id"]
    ids = [r["id"] for r in client.get("/persons", params={"q": "Pedro"}).json()["records"]]
    assert pid not in ids
    pending = [r["id"] for r in client.get("/moderation/pending").json()["records"]]
    assert pid in pending
    client.post(f"/moderation/{pid}/approve")
    ids = [r["id"] for r in client.get("/persons", params={"q": "Pedro"}).json()["records"]]
    assert pid in ids
