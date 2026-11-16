import os
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ai_config
import prompt
from character import CharacterConfig


def test_compact_messages_keep_persona_recent_context_and_current_text(monkeypatch):
    config = CharacterConfig()
    config.name = "Lumen"
    config.user_address = "Sam"
    config.personality = "Patient and curious. " + "温" * 1000
    config.speech_patterns = "Use short replies."
    config.raw_text = "RAW PERSONA SHOULD NOT BE SENT"
    monkeypatch.setattr(prompt, "get_config", lambda: config)
    monkeypatch.setattr(prompt, "resolve_user_entity_label", lambda: "Sam")
    history = [{"role": "user", "text": "Old turn to exclude"}] + [
        {"role": role, "text": f"Recent {index}: " + "🙂" * 1000}
        for index, role in enumerate(["assistant", "user", "assistant", "user", "assistant"])
    ]
    user_text = "Keep this text intact. 确认🙂"
    messages = prompt.build_fast_local_chat_messages(history, user_text)
    system = messages[0]["content"]
    assert all(fragment in system for fragment in ("Lumen", "Sam", "Patient and curious", "Use short replies"))
    assert config.raw_text not in system
    assert len(system.encode("utf-8")) < 1200
    assert len(messages) == 7
    assert all("Old turn" not in message["content"] for message in messages)
    assert all("�" not in message["content"] for message in messages)
    assert all(len(message["content"].encode("utf-8")) <= 240 for message in messages[1:-1])
    assert messages[-1] == {"role": "user", "content": user_text}


def test_fast_local_timeout_keeps_owner_cap_and_attempts_once(monkeypatch):
    runtime = {"host": "localhost:11434", "api_key": "ollama", "model": "test", "max_tokens": 32}
    monkeypatch.setattr(ai_config, "get_tier_config", lambda tier: runtime)
    complete = Mock(side_effect=TimeoutError("Request timed out"))
    client = Mock(base_url="http://localhost:11434/v1")
    client.with_options.return_value = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=complete)),
    )
    monkeypatch.setattr(ai_config, "get_tier_client", lambda tier: client)
    messages = [{"role": "user", "content": "Hello"}]
    with pytest.raises(TimeoutError, match="Request timed out"):
        prompt.call_fast_local_chat(messages)
    client.with_options.assert_called_once_with(max_retries=0)
    complete.assert_called_once_with(
        model="test", messages=messages, max_tokens=32, temperature=0.3,
    )


def test_fast_local_rejects_a_remote_sdk_client(monkeypatch):
    monkeypatch.setattr(prompt, "_get_ai_runtime_or_raise", lambda tier: {"model": "test"})
    client = Mock(base_url="https://example.test/v1")
    monkeypatch.setattr(ai_config, "get_tier_client", lambda tier: client)
    with pytest.raises(RuntimeError, match="requires a loopback provider"):
        prompt.call_fast_local_chat([{"role": "user", "content": "Hello"}])
    client.with_options.assert_not_called()


def test_core_memory_excerpt_keeps_recent_notes_with_a_utf8_budget(monkeypatch):
    monkeypatch.setattr(prompt, "get_config", CharacterConfig)
    monkeypatch.setattr(prompt, "resolve_user_entity_label", lambda: "Sam")
    blocks = {
        "human": "Old human note. " + "温" * 250 + "\nNew human note.",
        "persona": "Old relationship note. " + "🙂" * 250 + "\nNew relationship note.",
        "other": "Unrelated block should not be sent.",
    }
    baseline = prompt.build_fast_local_chat_messages([], "Hello")
    messages = prompt.build_fast_local_chat_messages([], "Hello", core_blocks=blocks)
    system = messages[0]["content"]
    assert "New human note." in system and "New relationship note." in system
    assert "Old" not in system and "Unrelated block" not in system and "�" not in system
    assert len(system.encode("utf-8")) - len(baseline[0]["content"].encode("utf-8")) < 850
    assert messages[-1] == baseline[-1] == {"role": "user", "content": "Hello"}


@pytest.mark.parametrize("live", [False, True], ids=["mock-provider", "live-ollama"])
def test_fast_route_recalls_only_current_account_core_memory(monkeypatch, tmp_path, live):
    if live and os.environ.get("SORA_TEST_FAST_MEMORY") != "1":
        pytest.skip("Set SORA_TEST_FAST_MEMORY=1 with local Ollama and qwen2.5:1.5b-instruct")

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SERVER_IP", "192.0.2.10")
    monkeypatch.setenv("SERVER_PORT", "5001")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    import app
    import attention_engine
    import auth
    import chat_timing
    import core
    import core_memory
    import curator
    import sleep_agent

    monkeypatch.setattr(auth, "_BASE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "_ADMIN_DIR", str(tmp_path / "_admin"))
    monkeypatch.setattr(app, "_is_client_mode", False)
    monkeypatch.setattr(app, "_client_mode_config", {})
    monkeypatch.setattr(curator, "start_loop_for_user", lambda *_: None)
    monkeypatch.setattr(core, "_QUIET_PERIOD", 0.02)
    monkeypatch.setattr(attention_engine, "get_attention_engine", lambda: SimpleNamespace(record_signal=lambda *_: None))
    monkeypatch.setattr(sleep_agent, "get_sleep_agent", lambda: SimpleNamespace(enqueue=lambda *_args, **_kwargs: None))

    def unexpected(*_args, **_kwargs):
        pytest.fail("Fast chat should not call full context or model-based preflight")

    monkeypatch.setattr(core, "_build_chat_context", unexpected)
    monkeypatch.setattr(prompt, "call_chat_preflight", unexpected)
    monkeypatch.setattr(ai_config, "_cache", None)
    monkeypatch.setattr(ai_config, "_client_cache", {})
    assert ai_config.update_tier_config("chat", {
        "host": "127.0.0.1:11434/v1", "model": "qwen2.5:1.5b-instruct", "api_key": "ollama",
    })["ok"]

    if not live:
        def complete(*, messages, **kwargs):
            system = messages[0]["content"]
            assert "Relationship notes: We joke about early mornings." in system
            known_fruits = [fruit for fruit in ("mango", "blueberry") if fruit in system]
            assert len(known_fruits) == 1 and "tools" not in kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=known_fruits[0]))], usage=None,
            )

        provider = Mock(base_url="http://127.0.0.1:11434/v1")
        provider.with_options.return_value = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=complete)),
        )
        monkeypatch.setattr(ai_config, "get_tier_client", lambda tier: provider)

    client = app.app.test_client()
    accounts = auth.generate_invitation_codes(2, ip="192.0.2.10")
    for invitation, fruit, other in zip(accounts, ("mango", "blueberry"), ("blueberry", "mango")):
        login = client.post("/api/auth/login", json={"code": invitation})
        assert login.status_code == 200
        account = login.get_json()
        headers = {"Authorization": f"Bearer {account['token']}"}
        with app.app.test_request_context("/api/core-memory", headers=headers):
            assert auth.check_request() is None
            assert core_memory.append("human", f"The user's favorite fruit is {fruit}.", auto_consolidate=False)["ok"]
            assert core_memory.append("persona", "We joke about early mornings.", auto_consolidate=False)["ok"]
        settings = client.post("/api/user-settings", headers=headers, json={"local_text_chat_enabled": True})
        assert settings.status_code == 200
        assert client.get("/api/chat/history", headers=headers).get_json() == []

        started = time.monotonic()
        with chat_timing.capture(account["user_id"]) as trace:
            answer = client.post("/api/chat", headers=headers, json={"text": "What is my favorite fruit? Reply briefly."})
            assert answer.status_code == 200
            reply_id = answer.get_json()["msg_id"] + "_reply"
            deadline = started + (90 if live else 5)
            while time.monotonic() < deadline:
                history = client.get("/api/chat/history", headers=headers).get_json()
                reply = next((item for item in history if item["id"] == reply_id), None)
                if reply is not None:
                    break
                time.sleep(0.1)
            assert reply is not None
            assert trace.persistence_finished.wait(timeout=1)
            assert trace.policy == "reactive_fast"
            assert "memory_preflight" not in trace.stages
            assert len(trace.model_attempts) == 1 and trace.model_attempts[0]["succeeded"]

        text = reply["text"].lower()
        assert reply["role"] == "assistant" and fruit in text and other not in text, reply["text"]
        if live:
            print(f"{fruit}: {time.monotonic() - started:.2f}s · {reply['text']}")
