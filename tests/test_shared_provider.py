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
