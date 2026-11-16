import pytest


@pytest.fixture
def shared_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SERVER_IP", "192.0.2.10")
    monkeypatch.setenv("SERVER_PORT", "5001")

    import app
    import auth
    import curator
    import memory
    import storage

    monkeypatch.setattr(auth, "_BASE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "_ADMIN_DIR", str(tmp_path / "_admin"))
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(memory, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app, "_is_client_mode", False)
    monkeypatch.setattr(app, "_client_mode_config", {})
    monkeypatch.setattr(curator, "start_loop_for_user", lambda *_: None)
    monkeypatch.setattr(curator, "track_slot_change", lambda *_: None)

    return app.app


def sign_in(client, code):
    response = client.post("/api/auth/login", json={"code": code})
    assert response.status_code == 200
    return response.get_json()


def bearer(account):
    return {"Authorization": f"Bearer {account['token']}"}


@pytest.mark.parametrize("account_mode", ["invited", "existing_local"])
def test_independent_clients_share_only_their_account_memory(shared_backend, tmp_path, account_mode):
    import auth
    import core_memory
    import memory_router

    laptop = shared_backend.test_client()
    phone = shared_backend.test_client()
    phone.environ_base["REMOTE_ADDR"] = "192.0.2.20"
    other = shared_backend.test_client()
    other.environ_base["REMOTE_ADDR"] = "192.0.2.30"

    owner_code, other_code = auth.generate_invitation_codes(2, ip="192.0.2.10")
    other_account = sign_in(other, other_code)
    if account_mode == "invited":
        owner = sign_in(laptop, owner_code)
        phone_account = sign_in(phone, owner_code)
        assert owner["is_new"] is True
        assert phone_account["is_new"] is False
    else:
        # Provide the existing local account credential directly to the test client.
        # This exercises account data routing without simulating a pairing UI.
        owner = auth.get_or_create_local_single_device_user()
        phone_account = owner
    assert other_account["user_id"] != owner["user_id"]
    for client, account in ((laptop, owner), (phone, phone_account)):
        response = client.get("/api/auth/me", headers=bearer(account))
        assert response.status_code == 200
        assert response.get_json()["user_id"] == owner["user_id"]

    path = "projects/shared-audit.md"
    read = {"path": path}
    laptop_headers, phone_headers, other_headers = map(bearer, (owner, phone_account, other_account))
    assert laptop.post("/api/memory/write", headers=laptop_headers, json={
        "path": path, "content": "# Laptop project\nThe project starts on Monday.",
    }).status_code == 200
    initial = phone.get("/api/memory/read", query_string=read, headers=phone_headers)
    assert initial.status_code == 200
    assert "starts on Monday" in initial.get_json()["content"]
    etag = initial.headers["ETag"]
    assert phone.get("/api/memory/read", query_string=read,
                     headers={**phone_headers, "If-None-Match": etag}).status_code == 304
    assert phone.post("/api/memory/write", headers=phone_headers, json={
        "path": path, "mode": "append", "content": "Android added the test result.",
    }).status_code == 200

    updated = laptop.get("/api/memory/read", query_string=read,
                         headers={**laptop_headers, "If-None-Match": etag})
    assert updated.status_code == 200 and updated.headers["ETag"] != etag
    assert "starts on Monday" in updated.get_json()["content"]
    assert "Android added the test result." in updated.get_json()["content"]
    owner_root = tmp_path / "users" / owner["user_id"]
    assert (owner_root / "memory" / path).read_text(encoding="utf-8") == updated.get_json()["content"]

    # Seed a real slot and core block via the existing memory helpers inside the owner's context.
    with shared_backend.test_request_context("/api/core-memory", headers=laptop_headers):
        assert auth.check_request() is None
        assert core_memory.append("human", "Prefers local-only services.", auto_consolidate=False)["ok"]
        assert memory_router.upsert_slot("project", {
            "id": "shared-audit",
            "title": "Shared audit",
            "main_file": path,
            "status": "active",
        })

    slot_url = "/api/memory/slot/project/shared-audit"
    slot = phone.get(slot_url, headers=phone_headers)
    assert slot.status_code == 200
    assert slot.get_json()["main_md"] == updated.get_json()["content"]
    for client, headers in ((laptop, laptop_headers), (phone, phone_headers)):
        core_blocks = client.get("/api/core-memory", headers=headers).get_json()["blocks"]
        assert core_blocks["human"]["content"] == "Prefers local-only services."

    assert phone.get("/api/memory/read", query_string=read).status_code == 401
    assert other.get("/api/memory/read", query_string=read, headers=other_headers).status_code == 404
    assert other.get(slot_url, headers=other_headers).status_code == 404
    assert other.get("/api/core-memory", headers=other_headers).get_json()["blocks"]["human"]["content"] == ""
