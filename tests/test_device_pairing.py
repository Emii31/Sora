from concurrent.futures import ThreadPoolExecutor
import time

import pytest

import auth
import device_pairing
from test_shared_memory_backend import bearer, shared_backend  # noqa: F401


@pytest.fixture
def paired_backend(shared_backend, monkeypatch):
    monkeypatch.setenv("SORA_LOCAL_PAIRING", "1")
    return shared_backend


def test_phone_shares_existing_account_and_can_be_revoked(paired_backend, tmp_path):
    laptop = paired_backend.test_client()
    phone = paired_backend.test_client()
    phone.environ_base["REMOTE_ADDR"] = "192.0.2.20"
    secure = {"base_url": "https://sora.test"}
    account = auth.get_or_create_local_single_device_user()
    owner = bearer(account)
    issued = laptop.post("/api/pairing/code", headers=owner)
    assert issued.status_code == 201
    assert "no-store" in issued.headers["Cache-Control"]
    code = issued.json["code"]
    assert 0 < issued.json["expires_at"] - time.time() <= 300
    assert phone.post("/api/pairing/redeem", json={"code": code}).status_code == 403
    paired = phone.post("/api/pairing/redeem", json={"code": code, "name": "Motorola"}, **secure)
    assert paired.status_code == 201
    assert "no-store" in paired.headers["Cache-Control"]
    assert paired.json["user_id"] == account["user_id"]
    assert paired.json["token"] != account["token"]
    assert phone.post("/api/pairing/redeem", json={"code": code}, **secure).status_code == 401
    device = bearer(paired.json)
    path = "self/pairing-example.md"
    assert phone.post("/api/memory/write", headers=device, **secure, json={
        "path": path, "content": "A synthetic shared fact."
    }).status_code == 200
    owner_file = tmp_path / "users" / account["user_id"] / "memory" / path
    assert owner_file.read_text() == "A synthetic shared fact."
    assert laptop.get("/api/memory/read", query_string={"path": path}, headers=owner).json["content"] == owner_file.read_text()
    assert phone.get("/api/auth/me", headers=device, **secure).json == {
        "user_id": account["user_id"], "is_admin": False
    }
    for route in ("/api/auth/invitation", "/api/owner/ai-config", "/api/pairing/devices", "/api/admin/users"):
        assert phone.get(route, headers=device, **secure).status_code == 403
    assert phone.post("/api/chat", headers=device, data={"text": "hello"}, **secure).status_code == 403
    assert phone.get("/api/auth/me", headers=device).status_code == 403
    assert phone.get("/api/auth/me", query_string={"token": paired.json["token"]}, **secure).status_code == 401

    listing = laptop.get("/api/pairing/devices", headers=owner).json["devices"]
    assert len(listing) == 1 and listing[0]["name"] == "Motorola"
    assert set(listing[0]) == {"id", "name", "created_at"}
    store = (tmp_path / "_admin/local_pairing.sqlite3").read_bytes()
    assert code.encode() not in store and paired.json["token"].encode() not in store
    spare_code = laptop.post("/api/pairing/code", headers=owner).json["code"]
    spare = phone.post("/api/pairing/redeem", json={"code": spare_code}, **secure)
    assert spare.status_code == 201 and spare.json["device_id"] != paired.json["device_id"]
    assert laptop.delete("/api/pairing/devices/" + paired.json["device_id"], headers=owner).status_code == 204
    assert phone.get("/api/auth/me", headers=device, **secure).status_code == 401
    assert phone.get("/api/auth/me", headers=bearer(spare.json), **secure).status_code == 200
    assert laptop.get("/api/auth/me", headers=owner).status_code == 200


def test_pairing_is_opt_in_and_owner_management_is_loopback_only(shared_backend, monkeypatch):
    account = auth.get_or_create_local_single_device_user()
    headers = bearer(account)
    client = shared_backend.test_client()
    monkeypatch.delenv("SORA_LOCAL_PAIRING", raising=False)
    assert client.post("/api/pairing/code", headers=headers).status_code == 404
    assert client.post("/api/pairing/redeem", json={"code": "unknown"}).status_code == 404
    monkeypatch.setenv("SORA_LOCAL_PAIRING", "1")
    assert client.post("/api/pairing/code", query_string={"token": account["token"]}).status_code == 403
    assert client.post("/api/pairing/code", headers=headers, base_url="https://sora.test",
                       environ_overrides={"REMOTE_ADDR": "192.0.2.20"}).status_code == 403
    assert client.post("/api/pairing/redeem", json=[1]).status_code == 400


def test_expiry_and_concurrent_redeem_are_checked_atomically(tmp_path, monkeypatch):
    now = 1000
    monkeypatch.setattr(device_pairing.time, "time", lambda: now)
    expiring, expires = device_pairing.issue_code(tmp_path, "u_example")
    now = expires
    assert device_pairing.redeem_code(tmp_path, expiring, "Phone", lambda _: True) is None
    code, _ = device_pairing.issue_code(tmp_path, "u_example")
    assert device_pairing.redeem_code(tmp_path, code, "Phone", lambda _: False) is None
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: device_pairing.redeem_code(tmp_path, code, "Phone", lambda uid: uid == "u_example"), range(8)))
    [phone] = [item for item in claims if item]
    assert device_pairing.user_for_token(tmp_path, phone["token"]) == "u_example"
    assert device_pairing.revoke_phone(tmp_path, "u_other", phone["device_id"]) is False
    assert device_pairing.user_for_token(tmp_path, phone["token"]) == "u_example"
