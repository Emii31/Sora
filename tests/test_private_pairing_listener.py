import pytest

import auth
from scripts.serve_private_pairing import wifi_address, wifi_app
from test_shared_memory_backend import bearer, shared_backend  # noqa: F401


@pytest.mark.parametrize("address", ["0.0.0.0", "127.0.0.1", "8.8.8.8", "100.64.0.1", "::"])
def test_wifi_listener_rejects_wildcard_loopback_and_non_lan_address(address):
    with pytest.raises(ValueError, match="private IPv4"):
        wifi_address(address)


def test_wifi_listener_uses_same_account_with_phone_only_access(shared_backend, monkeypatch):
    monkeypatch.setenv("SORA_LOCAL_PAIRING", "1")
    owner = shared_backend.test_client()
    account = auth.get_or_create_local_single_device_user()
    owner_headers = bearer(account)
    code = owner.post("/api/pairing/code", headers=owner_headers).json["code"]
    from werkzeug.test import Client
    from werkzeug.wrappers import Response

    wifi = Client(wifi_app(shared_backend), Response)
    secure = {"base_url": "https://192.168.1.2", "environ_overrides": {"REMOTE_ADDR": "192.168.1.3"}}
    assert wifi.get("/api/health", **secure).status_code == 200
    assert wifi.get("/api/health").status_code == 404
    assert wifi.get("/app", **secure).status_code == 404
    assert wifi.post("/api/auth/login", headers=owner_headers, **secure).status_code == 404
    assert wifi.post("/api/pairing/code", headers=owner_headers, **secure).status_code == 404
    assert wifi.get("/api/pairing/devices", headers=owner_headers, **secure).status_code == 404
    assert wifi.get("/api/auth/me", headers=owner_headers, **secure).status_code == 401
    assert wifi.get("/api/memory/tree", **secure).status_code == 401
    response = wifi.post("/api/pairing/redeem", json={"code": code}, **secure)
    assert response.status_code == 201
    phone_headers = bearer(response.json)
    assert wifi.get("/api/auth/me", headers=phone_headers, **secure).json["user_id"] == account["user_id"]
    assert wifi.get("/api/owner/ai-config", headers=phone_headers, **secure).status_code == 404
    assert wifi.get("/api/auth/me", query_string={"token": response.json["token"]}, **secure).status_code == 401
    assert owner.get("/api/pairing/devices", headers=owner_headers).status_code == 200
