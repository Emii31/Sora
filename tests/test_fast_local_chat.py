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
