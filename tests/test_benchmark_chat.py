import importlib
import os
import sys
import tempfile
import json
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_benchmark_user_settings_persistence_and_policy(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)

    import auth
    auth._BASE_DATA_DIR = data_dir
    auth._ADMIN_DIR = admin_dir

    # Seed ai_config.json with a loopback host so local fast text chat policy triggers
    config_path = os.path.join(admin_dir, "ai_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "tiers": {
                "chat": {"host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct"}
            }
        }, f, indent=2)

    import ai_config
    ai_config.invalidate_cache()

    import app as app_mod
    app_mod.app.config["TESTING"] = True
    client = app_mod.app.test_client()

    local = auth.get_or_create_local_single_device_user()
    token = local["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    environ = {"REMOTE_ADDR": "127.0.0.1"}

    # Test setting fast_mode = True via authenticated /api/user-settings route
    post_res = client.post(
        "/api/user-settings",
        json={"local_text_chat_enabled": True},
        headers=headers,
        environ_base=environ
    )
    assert post_res.status_code == 200

    # Read back and verify persistence via GET /api/user-settings
    get_res = client.get(
        "/api/user-settings",
        headers=headers,
        environ_base=environ
    )
    assert get_res.status_code == 200
    data = get_res.get_json()
    assert data["settings"]["local_text_chat_enabled"] is True

    # Test policy resolution in request context with authenticated request
    import core
    with client.application.test_request_context(path="/api/chat", method="POST", headers=headers, environ_base=environ):
        auth.check_request()
        policy = core._resolve_chat_agent_policy(user_text="Matched test prompt")
        assert policy["mode"] == "reactive_fast"

    # Test setting fast_mode = False via authenticated /api/user-settings route
    client.post(
        "/api/user-settings",
        json={"local_text_chat_enabled": False},
        headers=headers,
        environ_base=environ
    )
    get_res_full = client.get(
        "/api/user-settings",
        headers=headers,
        environ_base=environ
    )
    assert get_res_full.get_json()["settings"]["local_text_chat_enabled"] is False

    with client.application.test_request_context(path="/api/chat", method="POST", headers=headers, environ_base=environ):
        auth.check_request()
        policy_full = core._resolve_chat_agent_policy(user_text="Matched test prompt")
        assert policy_full["mode"] == "v4_pro"


def test_benchmark_harness_success_and_reply_matching(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)

    import auth
    auth._BASE_DATA_DIR = data_dir
    auth._ADMIN_DIR = admin_dir

    import app as app_mod
    app_mod.app.config["TESTING"] = True
    client = app_mod.app.test_client()

    local = auth.get_or_create_local_single_device_user()
    token = local["token"]

    import storage
    import core

    def mock_receive(text, image=None, device_id=""):
        msg_id = "msg_" + os.urandom(4).hex()
        reply_id = msg_id + "_reply"
        chat_history = [
            {"id": msg_id, "role": "user", "text": text, "time": "2026-11-13 12:00:00"},
            {"id": reply_id, "role": "assistant", "text": "Valid matched benchmark response.", "time": "2026-11-13 12:00:01"}
        ]
        storage.write_json(storage.chat_history_path(), chat_history)
        return {"ok": True, "msg_id": msg_id}

    monkeypatch.setattr(core, "receive_chat_message", mock_receive)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = client.post(
        "/api/chat",
        json={"text": "Matched prompt text"},
        headers=headers,
        environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    msg_id = data["msg_id"]
    expected_reply_id = msg_id + "_reply"

    hist_res = client.get(
        "/api/chat/history?limit=50",
        headers=headers,
        environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert hist_res.status_code == 200
    history = hist_res.get_json()
    reply_texts = [m["text"] for m in history if m.get("id") == expected_reply_id]
    assert len(reply_texts) == 1
    assert reply_texts[0] == "Valid matched benchmark response."
