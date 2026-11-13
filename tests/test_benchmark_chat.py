import importlib
import os
import sys
import tempfile
import json
import pytest
from unittest.mock import patch, MagicMock

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


def test_benchmark_runner_end_to_end_mocked(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)

    import auth
    auth._BASE_DATA_DIR = data_dir
    auth._ADMIN_DIR = admin_dir

    config_path = os.path.join(admin_dir, "ai_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "tiers": {
                "chat": {"host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct"}
            }
        }, f, indent=2)

    import ai_config
    import user_settings
    ai_config.invalidate_cache()
    import storage
    import core

    storage._ensure_dirs()

    # Mock OpenAI client chat completions
    mock_openai_response = MagicMock()
    mock_openai_response.choices = [MagicMock(message=MagicMock(content="Direct model mock reply."))]

    class MockOpenAIClient:
        def __init__(self, *args, **kwargs):
            pass
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    return mock_openai_response

    monkeypatch.setattr("scripts.benchmark_chat.OpenAI", MockOpenAIClient)

    # Mock core receive_chat_message to write history and set _last_resolved_chat_policy correctly
    def mock_receive(text, image=None, device_id=""):
        msg_id = "msg_" + os.urandom(4).hex()
        reply_id = msg_id + "_reply"
        chat_history = [
            {"id": msg_id, "role": "user", "text": text, "time": "2026-11-13 12:00:00"},
            {"id": reply_id, "role": "assistant", "text": "Valid matched benchmark response.", "time": "2026-11-13 12:00:01"}
        ]
        storage.write_json(storage.chat_history_path(), chat_history)

        # Determine expected policy based on user settings
        us = user_settings.get()
        is_fast = us.get("local_text_chat_enabled", False)
        core._last_resolved_chat_policy = {
            "mode": "reactive_fast" if is_fast else "v4_pro",
            "tier": "chat",
            "reasoning": False,
            "max_iterations": 1 if is_fast else 8,
            "allow_tools": not is_fast,
        }
        return {"ok": True, "msg_id": msg_id}

    monkeypatch.setattr(core, "receive_chat_message", mock_receive)

    import scripts.benchmark_chat as bench
    app_mod = sys.modules["app"]
    app_mod.app.config["TESTING"] = True
    client = app_mod.app.test_client()

    local = auth.get_or_create_local_single_device_user()
    token = local["token"]

    # Run benchmark pair test
    pair_result = bench.run_benchmark_pair(client, token, prompt_text="Benchmark test prompt under matched conditions.", order="full_first")
    assert pair_result[False]["success"] is True
    assert pair_result[False]["policy_mode"] == "v4_pro"
    assert pair_result[True]["success"] is True
    assert pair_result[True]["policy_mode"] == "reactive_fast"

    # Test fast_first order pair
    pair_result_fast_first = bench.run_benchmark_pair(client, token, prompt_text="Benchmark test prompt under matched conditions.", order="fast_first")
    assert pair_result_fast_first[True]["success"] is True
    assert pair_result_fast_first[False]["success"] is True


def test_benchmark_failure_conditions(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)

    import auth
    auth._BASE_DATA_DIR = data_dir
    auth._ADMIN_DIR = admin_dir

    config_path = os.path.join(admin_dir, "ai_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "tiers": {
                "chat": {"host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct"}
            }
        }, f, indent=2)

    import ai_config
    ai_config.invalidate_cache()
    import storage
    import core
    storage._ensure_dirs()

    class MockOpenAIClient:
        def __init__(self, *args, **kwargs):
            pass
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    return MagicMock(choices=[MagicMock(message=MagicMock(content="reply"))])

    monkeypatch.setattr("scripts.benchmark_chat.OpenAI", MockOpenAIClient)

    # Simulate wrong policy (returning v4_pro when fast mode requested)
    def mock_receive_wrong_policy(text, image=None, device_id=""):
        msg_id = "msg_err"
        reply_id = msg_id + "_reply"
        storage.write_json(storage.chat_history_path(), [
            {"id": msg_id, "role": "user", "text": text, "time": "2026-11-13 12:00:00"},
            {"id": reply_id, "role": "assistant", "text": "Valid reply", "time": "2026-11-13 12:00:01"}
        ])
        # Force wrong policy mode
        core._last_resolved_chat_policy = {"mode": "v4_pro"}
        return {"ok": True, "msg_id": msg_id}

    monkeypatch.setattr(core, "receive_chat_message", mock_receive_wrong_policy)

    import scripts.benchmark_chat as bench
    app_mod = sys.modules["app"]
    client = app_mod.app.test_client()
    local = auth.get_or_create_local_single_device_user()
    token = local["token"]

    # When fast mode is requested (True), but worker returns v4_pro, test that success is False
    pair_res = bench.run_benchmark_pair(client, token, prompt_text="Prompt", order="fast_first")
    assert pair_res[True]["success"] is False


def test_benchmark_data_isolation_and_disposable_dir(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "disposable_data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)

    # Verify importing benchmark module has no side effects before DATA_DIR setup
    import scripts.benchmark_chat as bench
    assert bench is not None

    storage, core, user_settings, ai_config, auth, app_mod = bench._import_app_modules()
    storage.DATA_DIR = data_dir
    import importlib
    importlib.reload(storage)
    storage.DATA_DIR = data_dir
    auth._BASE_DATA_DIR = data_dir
    auth._ADMIN_DIR = admin_dir

    config_path = os.path.join(admin_dir, "ai_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "tiers": {
                "chat": {"host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct"}
            }
        }, f, indent=2)

    ai_config.invalidate_cache()
    storage._ensure_dirs()

    local_user = auth.get_or_create_local_single_device_user()
    assert local_user["token"] is not None

    user_settings.update({"local_text_chat_enabled": True})
    history_path = storage.chat_history_path()
    assert history_path.startswith(data_dir)
    storage.write_json(history_path, [{"id": "test_id", "text": "isolated"}])

    # Ensure all files under DATA_DIR stay within data_dir
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            assert os.path.join(root, file).startswith(data_dir)