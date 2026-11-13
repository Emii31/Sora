import json
import os
import pytest
import ai_config
from unittest.mock import patch, MagicMock

def test_shared_provider_config_resolution(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)

    config_path = os.path.join(admin_dir, "ai_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "shared": {
                "host": "shared-host.com",
                "api_key": "shared-key"
            },
            "tiers": {
                "chat": {"model": "chat-model"},
                "memory": {"host": "memory-host.com", "api_key": "memory-key", "model": "memory-model"}
            }
        }, f, indent=2)

    ai_config.invalidate_cache()

    # Chat should inherit shared host/key
    chat_cfg = ai_config.get_tier_config("chat")
    assert chat_cfg["host"] == "shared-host.com"
    assert chat_cfg["api_key"] == "shared-key"
    assert chat_cfg["model"] == "chat-model"

    # Vision should inherit shared host/key
    vision_cfg = ai_config.get_tier_config("vision")
    assert vision_cfg["host"] == "shared-host.com"
    assert vision_cfg["api_key"] == "shared-key"

    # Memory should use its own overrides
    mem_cfg = ai_config.get_tier_config("memory")
    assert mem_cfg["host"] == "memory-host.com"
    assert mem_cfg["api_key"] == "memory-key"
    assert mem_cfg["model"] == "memory-model"


def test_config_precedence(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)

    monkeypatch.setenv("AI_CHAT_HOST", "env-host.com")

    config_path = os.path.join(admin_dir, "ai_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "shared": {"host": "shared-host.com"},
            "tiers": {"chat": {"host": "override-host.com"}}
        }, f, indent=2)

    ai_config.invalidate_cache()

    # Should use override-host.com
    chat_cfg = ai_config.get_tier_config("chat")
    assert chat_cfg["host"] == "override-host.com"


def test_update_shared_config_and_public_masking(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    os.makedirs(os.path.join(data_dir, "_admin"), exist_ok=True)
    ai_config.invalidate_cache()

    res = ai_config.update_shared_config({
        "host": "api.provider.test/v1",
        "api_key": "sk-secret-token-12345"
    })
    assert res["ok"] is True
    pub = ai_config.get_public_config()
    assert pub["shared"]["host"] == "api.provider.test/v1"
    assert pub["shared"]["has_api_key"] is True
    assert pub["shared"]["api_key_masked"] == "sk-s***2345"


def test_automatic_model_selection_mocked(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)
    ai_config.invalidate_cache()

    # Mock discover_provider_models to return sample model list
    monkeypatch.setattr(ai_config, "discover_provider_models", lambda host, key: ["qwen2.5:1.5b-instruct", "qwen2.5-vl:7b"])

    ai_config.update_shared_config({
        "host": "localhost:11434",
        "api_key": "ollama"
    })

    chat_cfg = ai_config.get_tier_config("chat")
    assert chat_cfg["model"] == "qwen2.5:1.5b-instruct"

    vision_cfg = ai_config.get_tier_config("vision")
    assert vision_cfg["model"] == "qwen2.5-vl:7b"
    assert vision_cfg["supports_images"] is True


def test_endpoint_change_clears_key_and_prevents_credential_reuse(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    os.makedirs(os.path.join(data_dir, "_admin"), exist_ok=True)
    ai_config.invalidate_cache()

    discovered_calls = []
    def mock_discover(host, key):
        discovered_calls.append((host, key))
        return ["model:instruct"]

    monkeypatch.setattr(ai_config, "discover_provider_models", mock_discover)

    ai_config.update_shared_config({
        "host": "provider-a.com",
        "api_key": "secret-key-A"
    })
    assert ai_config.get_public_config()["shared"]["has_api_key"] is True
    discovered_calls.clear()

    # Update to a different endpoint without api_key should clear key and send no discovery request with old key
    ai_config.update_shared_config({
        "host": "provider-b.com"
    })
    pub = ai_config.get_public_config()
    assert pub["shared"]["host"] == "provider-b.com"
    assert pub["shared"]["has_api_key"] is False
    assert len(discovered_calls) == 0


def test_same_endpoint_blank_update_preserves_credential(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    os.makedirs(os.path.join(data_dir, "_admin"), exist_ok=True)
    ai_config.invalidate_cache()

    ai_config.update_shared_config({
        "host": "provider-a.com",
        "api_key": "secret-key-A"
    })
    assert ai_config.get_public_config()["shared"]["has_api_key"] is True

    # Same endpoint spelling update (e.g., adding /v1) without api_key preserves credential
    ai_config.update_shared_config({
        "host": "provider-a.com/v1"
    })
    pub = ai_config.get_public_config()
    assert pub["shared"]["has_api_key"] is True


def test_explicit_clearing_and_replacement_key(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    os.makedirs(os.path.join(data_dir, "_admin"), exist_ok=True)
    ai_config.invalidate_cache()

    ai_config.update_shared_config({
        "host": "provider-a.com",
        "api_key": "secret-key-A"
    })

    # Explicit clear
    ai_config.update_shared_config({
        "clear_api_key": True
    })
    assert ai_config.get_public_config()["shared"]["has_api_key"] is False

    # New endpoint with replacement key
    ai_config.update_shared_config({
        "host": "provider-c.com",
        "api_key": "secret-key-C"
    })
    pub = ai_config.get_public_config()
    assert pub["shared"]["host"] == "provider-c.com"
    assert pub["shared"]["has_api_key"] is True


def test_ping_tier_inheriting_does_not_create_override(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    admin_dir = os.path.join(data_dir, "_admin")
    os.makedirs(admin_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)
    ai_config.invalidate_cache()

    ai_config.update_shared_config({
        "host": "shared-provider.com",
        "api_key": "shared-key"
    })
    ai_config.update_tier_config("chat", {"model": "gpt-4o-mini"})

    # Verify chat inherits shared host
    assert ai_config.get_tier_config("chat")["host"] == "shared-provider.com"

    # Mock OpenAI client for ping_tier
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock()
    with patch("openai.OpenAI", return_value=mock_client):
        res = ai_config.ping_tier("chat")
        assert res["ok"] is True

    # Verify that pinging chat did NOT create a tier override for host in saved json
    saved = ai_config._load_saved()
    assert "chat" not in saved.get("tiers", {}) or "host" not in saved["tiers"]["chat"]
    assert ai_config.get_tier_config("chat")["host"] == "shared-provider.com"


def test_capability_based_model_selection_ambiguous_and_vision(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    os.makedirs(os.path.join(data_dir, "_admin"), exist_ok=True)
    ai_config.invalidate_cache()

    # Ambiguous / non-text models without text evidence
    monkeypatch.setattr(ai_config, "discover_provider_models", lambda host, key: ["model-embedding", "model-rerank"])

    ai_config.update_shared_config({
        "host": "localhost:11434",
        "api_key": "ollama"
    })

    chat_cfg = ai_config.get_tier_config("chat")
    # Should leave model empty because capability is ambiguous / unknown for chat
    assert chat_cfg["model"] == ""


def test_auto_model_invalidated_on_connection_change(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    os.makedirs(os.path.join(data_dir, "_admin"), exist_ok=True)
    ai_config.invalidate_cache()

    monkeypatch.setattr(ai_config, "discover_provider_models", lambda host, key: ["model-a:instruct"] if "provider-a" in host else ["model-b:instruct"])

    ai_config.update_shared_config({
        "host": "provider-a.com",
        "api_key": "key-a"
    })
    assert ai_config.get_tier_config("chat")["model"] == "model-a:instruct"

    ai_config.update_shared_config({
        "host": "provider-b.com",
        "api_key": "key-b"
    })
    assert ai_config.get_tier_config("chat")["model"] == "model-b:instruct"


def test_explicit_override_preserved(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    os.makedirs(os.path.join(data_dir, "_admin"), exist_ok=True)
    ai_config.invalidate_cache()

    monkeypatch.setattr(ai_config, "discover_provider_models", lambda host, key: ["auto-model:instruct"])

    ai_config.update_shared_config({
        "host": "provider-a.com",
        "api_key": "key-a"
    })
    ai_config.update_tier_config("chat", {"model": "my-explicit-model"})
    assert ai_config.get_tier_config("chat")["model"] == "my-explicit-model"

    ai_config.update_shared_config({
        "host": "provider-b.com",
        "api_key": "key-b"
    })
    assert ai_config.get_tier_config("chat")["model"] == "my-explicit-model"


def test_discovery_exact_endpoint_and_key(tmp_path, monkeypatch):
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    os.makedirs(os.path.join(data_dir, "_admin"), exist_ok=True)
    ai_config.invalidate_cache()

    passed_args = []
    def mock_discover(host, key):
        passed_args.append((host, key))
        return ["chat-model:instruct"]

    monkeypatch.setattr(ai_config, "discover_provider_models", mock_discover)

    ai_config.update_shared_config({
        "host": "custom-endpoint.test/v1",
        "api_key": "custom-secret-key"
    })

    assert len(passed_args) > 0
    assert any(h == "custom-endpoint.test/v1" and k == "custom-secret-key" for h, k in passed_args)
