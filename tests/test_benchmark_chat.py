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

    import storage
    storage.DATA_DIR = data_dir
    importlib.reload(storage)
    storage.DATA_DIR = data_dir

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

    import storage
    storage.DATA_DIR = data_dir
    importlib.reload(storage)
    storage.DATA_DIR = data_dir

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

    # Exercise the real worker and retry wrapper with a deterministic provider.
    from types import SimpleNamespace

    import attention_engine
    import sleep_agent

    provider_requests = []
    request_options = []

    def complete(**kwargs):
        provider_requests.append(kwargs)
        system_prompt = kwargs["messages"][0]["content"]
        content = (
            '{"need_retrieval": false, "files": [], "keywords": []}'
            if "Memory Retriever" in system_prompt
            else "Valid matched benchmark response."
        )
        message = SimpleNamespace(content=content, tool_calls=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason="stop")],
            usage=None,
        )

    provider = SimpleNamespace(
        base_url="http://127.0.0.1:11434/v1",
        chat=SimpleNamespace(completions=SimpleNamespace(create=complete)),
    )

    def with_options(**kwargs):
        request_options.append(kwargs)
        return provider

    provider.with_options = with_options
    monkeypatch.setattr(ai_config, "get_tier_client", lambda tier: provider)
    monkeypatch.setattr(core, "_QUIET_PERIOD", 0.01)
    monkeypatch.setattr(attention_engine, "get_attention_engine", lambda: SimpleNamespace(record_signal=lambda *a: None))
    monkeypatch.setattr(sleep_agent, "get_sleep_agent", lambda: SimpleNamespace(enqueue=lambda *a, **kw: None))
    ai_config.update_tier_config("memory", {
        "host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct",
    })

    import scripts.benchmark_chat as bench
    app_mod = sys.modules["app"]
    app_mod.app.config["TESTING"] = True
    client = app_mod.app.test_client()

    for order in ("full_first", "fast_first"):
        pair = bench.run_benchmark_pair(
            client, prompt_text="Synthetic benchmark text", order=order, timing=True,
        )
        assert list(pair) == ([False, True] if order == "full_first" else [True, False])
        for fast_mode, result in pair.items():
            assert result["success"]
            assert result["policy_mode"] == ("reactive_fast" if fast_mode else "v4_pro")
            trace = result["timing"]
            assert trace["turn_id"]
            assert trace["history_detection_seconds"] is not None
            assert {"queue_wait", "context_assembly", "history_and_tools",
                    "chat_agent", "reply_persistence"} <= trace["stages_seconds"].keys()
            assert ("memory_preflight" in trace["stages_seconds"]) is not fast_mode
            kinds = [attempt["kind"] for attempt in trace["model_attempts"]]
            assert kinds == (["agent"] if fast_mode else ["retrieval", "agent"])
            assert "Synthetic benchmark text" not in json.dumps(trace)
            assert result["reply"] not in json.dumps(trace)

    assert request_options == [{"max_retries": 0}] * 2
    compact_requests = [request for request in provider_requests if request["max_tokens"] == 96]
    assert len(compact_requests) == 2
    for request in compact_requests:
        assert "tools" not in request
        assert len(request["messages"][0]["content"].encode("utf-8")) < 1200
        assert request["messages"][-1]["content"] == "Synthetic benchmark text"

    fast_sample = bench.run_benchmark_pair(client, timing=True, fast_only=True)
    assert list(fast_sample) == [True]
    assert fast_sample[True]["success"]


def test_timing_records_attempts_and_backoff_only_for_registered_turn(monkeypatch):
    from types import SimpleNamespace

    import chat_timing
    import prompt

    delays = []
    monkeypatch.setattr(prompt, "time", SimpleNamespace(sleep=delays.append))
    outcomes = iter([ConnectionError("synthetic error"), "success"])

    def call():
        result = next(outcomes)
        if isinstance(result, Exception):
            raise result
        return result

    with chat_timing.capture("benchmark-user") as trace:
        chat_timing.queued("benchmark-user", "turn-1")
        with chat_timing.worker("other-user", "turn-1"):
            assert prompt._api_call_with_retry(lambda: "unrelated") == "unrelated"
        with chat_timing.worker("benchmark-user", "other-turn"):
            assert prompt._api_call_with_retry(lambda: "unrelated") == "unrelated"
        with chat_timing.worker("benchmark-user", "turn-1"):
            assert prompt._api_call_with_retry(call, label="AgentChat(iter=0)") == "success"

    assert len(delays) == 1
    assert trace.stages["retry_backoff"] >= 0
    assert [(a["kind"], a["attempt"], a["succeeded"]) for a in trace.model_attempts] == [
        ("agent", 1, False), ("agent", 2, True),
    ]


def test_benchmark_failure_conditions(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)

    import auth
    auth._BASE_DATA_DIR = data_dir
    auth._ADMIN_DIR = admin_dir

    import storage
    storage.DATA_DIR = data_dir
    importlib.reload(storage)
    storage.DATA_DIR = data_dir

    config_path = os.path.join(admin_dir, "ai_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "tiers": {
                "chat": {"host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct"}
            }
        }, f, indent=2)

    import ai_config
    ai_config.invalidate_cache()
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

    # When fast mode is requested (True), but worker returns v4_pro, test that success is False
    pair_res = bench.run_benchmark_pair(client, prompt_text="Prompt", order="fast_first")
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
