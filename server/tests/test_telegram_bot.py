# Telegram webhook adapter (plan-14 §5). TEST DATA — NOT REAL.

CHAT_ID = 555


def _post(client, text=None, chat_id=CHAT_ID):
    msg = {"chat": {"id": chat_id}}
    if text is not None:
        msg["text"] = text
    return client.post("/webhooks/telegram", json={"message": msg})


def test_reportar_creates_telegram_draft(client):
    _post(client, "/reportar")
    _post(client, "Pedro Pérez")
    _post(client, "V-12345678")
    _post(client, "Refugio Norte")
    res = _post(client, "desaparecido")
    draft = res.json()["draft"]
    assert draft["name"] == "Pedro Pérez"
    assert draft["source"] == "telegram"
    assert draft["reviewed"] == 0


def test_buscar_returns_approved_record(client):
    # Build + approve a record via the bot flow.
    _post(client, "/reportar", chat_id=600)
    _post(client, "María López", chat_id=600)
    _post(client, "V-22222222", chat_id=600)
    _post(client, "Sur", chat_id=600)
    draft = _post(client, "desaparecida", chat_id=600).json()["draft"]
    client.post(f"/moderation/{draft['id']}/approve")

    res = _post(client, "/buscar María", chat_id=601)
    assert "María López" in res.json()["reply"]


def test_reportar_midflow_resets_to_name(client):
    _post(client, "/reportar", chat_id=700)
    _post(client, "Nombre Viejo", chat_id=700)  # answers await_name → now await_cedula
    res = _post(client, "/reportar", chat_id=700)  # restart mid-flow
    # Engine should be asking for the name again, not consuming it as a cédula.
    assert "nombre" in res.json()["reply"].lower()


def test_ayuda_returns_help_without_resetting(client):
    _post(client, "/reportar", chat_id=800)
    _post(client, "Juan Pérez", chat_id=800)  # now at await_cedula
    res = _post(client, "/ayuda", chat_id=800)
    assert "Comandos" in res.json()["reply"]
    # Flow not reset: the next answer is taken as the cédula, finishing later steps.
    _post(client, "V-33333333", chat_id=800)
    _post(client, "Este", chat_id=800)
    final = _post(client, "desaparecido", chat_id=800).json()["draft"]
    assert final["name"] == "Juan Pérez"
    assert final["cedula"] == "V-33333333"
