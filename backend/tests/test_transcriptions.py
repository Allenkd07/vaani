def create(client, **overrides):
    payload = {"text": "Aaj ka meeting 5 baje hai, please be on time", "languages": "hi,en", "duration_sec": 4}
    payload.update(overrides)
    response = client.post("/api/transcriptions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_generates_title_from_text(client):
    created = create(client, text="one two three four five six seven eight nine ten")
    assert created["title"] == "one two three four five six seven eight…"


def test_mixed_script_text_round_trips(client):
    text = "नमस्ते, kal ka meeting cancel hai"
    created = create(client, text=text)
    assert client.get(f"/api/transcriptions/{created['id']}").json()["text"] == text
    assert client.get("/api/transcriptions", params={"search": "नमस्ते"}).json()["total"] == 1


def test_create_rejects_blank_text(client):
    assert client.post("/api/transcriptions", json={"text": "   "}).status_code == 422


def test_get_and_404(client):
    created = create(client, title="Standup")
    assert client.get(f"/api/transcriptions/{created['id']}").json()["title"] == "Standup"
    assert client.get("/api/transcriptions/9999").status_code == 404


def test_list_search_and_pagination(client):
    for i in range(3):
        create(client, title=f"Note {i}", text=f"hello {i}")
    create(client, title="Hindi", text="namaste duniya")

    page = client.get("/api/transcriptions", params={"size": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2

    found = client.get("/api/transcriptions", params={"search": "namaste"}).json()
    assert [item["title"] for item in found["items"]] == ["Hindi"]


def test_update(client):
    created = create(client)
    response = client.put(f"/api/transcriptions/{created['id']}", json={"title": "Renamed", "text": "edited text"})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert response.json()["text"] == "edited text"
    assert response.json()["languages"] == "hi,en"  # untouched fields are preserved


def test_delete(client):
    created = create(client)
    assert client.delete(f"/api/transcriptions/{created['id']}").status_code == 204
    assert client.get(f"/api/transcriptions/{created['id']}").status_code == 404


def test_live_websocket_streams_transcript(client):
    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_bytes(b"\x00\x00" * 1600)
        ws.send_json({"type": "stop"})
        assert ws.receive_json() == {"type": "interim", "text": "namaste", "language": "hi-IN"}
        assert ws.receive_json() == {"type": "final", "text": "namaste world 0", "language": "hi-IN"}
        assert ws.receive_json() == {"type": "done"}


def test_owner_cookie_is_issued_once_and_http_only(client):
    first = client.get("/api/health")
    cookie = first.headers["set-cookie"]
    assert cookie.startswith("vaani_owner=")
    assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    assert "set-cookie" not in client.get("/api/health").headers


def test_records_are_private_to_their_owner(client):
    mine = create(client, title="Mine")

    client.cookies.clear()  # a different browser
    assert client.get("/api/transcriptions").json()["total"] == 0
    assert client.get(f"/api/transcriptions/{mine['id']}").status_code == 404
    assert client.put(f"/api/transcriptions/{mine['id']}", json={"title": "Hijacked"}).status_code == 404
    assert client.delete(f"/api/transcriptions/{mine['id']}").status_code == 404


def test_invalid_owner_cookie_is_replaced(client):
    client.cookies.set("vaani_owner", "not-a-valid-token")
    response = client.get("/api/transcriptions")
    assert response.status_code == 200
    assert "vaani_owner=" in response.headers["set-cookie"]


def test_live_websocket_is_rate_limited_per_owner(client):
    client.get("/api/health")  # receive the owner cookie
    for _ in range(2):
        with client.websocket_connect("/ws/transcribe") as ws:
            assert ws.receive_json() == {"type": "ready"}
            ws.send_json({"type": "stop"})
            assert ws.receive_json() == {"type": "done"}

    with client.websocket_connect("/ws/transcribe") as ws:
        message = ws.receive_json()
        assert message["type"] == "error" and "2 recordings this hour" in message["message"]


def test_languages_accepts_any_language_codes(client):
    created = create(client, text="வணக்கம், hello", languages="ta,en")
    assert created["languages"] == "ta,en"


def test_languages_rejects_malformed_codes(client):
    for bad in ("Hindi", "hi-IN", "hi,,en", "hi;en"):
        response = client.post("/api/transcriptions", json={"text": "hello", "languages": bad})
        assert response.status_code == 422, bad
