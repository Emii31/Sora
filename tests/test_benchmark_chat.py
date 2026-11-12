import importlib
import os
import sys
import tempfile
import json
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_benchmark_harness_success(tmp_path, monkeypatch):
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

    # Mock core.receive_chat_message to instantly write user msg and expected reply to storage
    import storage
    import core

    def mock_receive(text, image=None, device_id=""):
        # Create user message
        msg_id = "msg_" + os.urandom(4).hex()
        reply_id = msg_id + "_reply"
        chat_history = [
            {"id": msg_id, "role": "user", "text": text, "time": "2026-11-13 12:00:00"},
            {"id": reply_id, "role": "assistant", "text": "This is a valid benchmark response.", "time": "2026-11-13 12:00:01"}
        ]
        storage.write_json(storage.chat_history_path(), chat_history)
        return {"ok": True, "msg_id": msg_id}

    monkeypatch.setattr(core, "receive_chat_message", mock_receive)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = client.post(
        "/api/chat",
        json={"text": "Hello benchmark"},
        headers=headers,
        environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    msg_id = data["msg_id"]
    expected_reply_id = msg_id + "_reply"

    # Verify history route returns the expected reply
    hist_res = client.get(
        "/api/chat/history?limit=50",
        headers=headers,
        environ_base={"REMOTE_ADDR": "127.0.0.1"}
    )
    assert hist_res.status_code == 200
    history = hist_res.get_json()
    reply_texts = [m["text"] for m in history if m.get("id") == expected_reply_id]
    assert len(reply_texts) == 1
    assert reply_texts[0] == "This is a valid benchmark response."


def test_benchmark_harness_fallback_detection():
    # Test fallback text detection logic used in benchmark runner
    fallback_strings = [
        "Error: Connection refused",
        "I haven't configured my models yet",
        "I couldn't connect to the model service",
        "I ran into a small issue",
        "小问题",
        "我还没有配置好"
    ]
    for s in fallback_strings:
        is_fallback = (
            s.lower().startswith("error:")
            or "i haven't configured my models yet" in s.lower()
            or "i couldn't connect to the model service" in s.lower()
            or "i ran into a small issue" in s.lower()
            or "小问题" in s
            or "我还没有配置好" in s
        )
        assert is_fallback is True

    valid_response = "Here is the result of your code benchmark."
    is_valid_fallback = (
        valid_response.lower().startswith("error:")
        or "i haven't configured my models yet" in valid_response.lower()
        or "i couldn't connect to the model service" in valid_response.lower()
        or "i ran into a small issue" in valid_response.lower()
        or "小问题" in valid_response
        or "我还没有配置好" in valid_response
    )
    assert is_valid_fallback is False
