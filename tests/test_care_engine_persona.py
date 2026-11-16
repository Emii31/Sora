"""AttentionEngine persona alignment after CareEngine retirement."""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _fake_cfg(**overrides):
    cfg = MagicMock()
    cfg.name = overrides.get("name", "Miru")
    cfg.user_address = overrides.get("user_address", "你")
    cfg.raw_text = overrides.get(
        "raw_text",
        "【性格】安静但在意\n【说话方式】短、轻、像真实陪伴",
    )
    return cfg


def test_attention_prompt_injects_full_soul_and_love_principle():
    import attention_engine

    cfg = _fake_cfg(raw_text="完整 soul 签名 SOUL_ATTENTION_123")
    with patch("character.get_config", return_value=cfg), \
         patch("prompt_identity.resolve_user_entity_label", return_value="用户"):
        prompt = attention_engine._build_attention_system_prompt()

    assert "完整 soul 签名 SOUL_ATTENTION_123" in prompt
    assert "爱与偏爱" in prompt
    assert "真的在乎" in prompt
    assert "第一人称" in prompt
    assert "speak_intent" in prompt


def test_attention_prompt_uses_entity_label_not_user_address():
    import attention_engine

    cfg = _fake_cfg(user_address="kiyo")
    with patch("character.get_config", return_value=cfg), \
         patch("prompt_identity.resolve_user_entity_label", return_value="李垦"):
        prompt = attention_engine._build_attention_system_prompt()

    assert "master" not in prompt
    assert "李垦的赛博陪伴者" in prompt
    assert "kiyo 的" not in prompt


def test_main_agent_proactive_mode_keeps_attention_continuity():
    import prompt

    system = prompt._build_agent_system_prompt(agent_mode="proactive")

    assert "Proactive Mode" in system
    assert "My Recently Unspoken Thoughts" in system
    assert "AttentionEngine" in system
    assert "natural, short, and warm" in system


def test_main_agent_prompt_normalizes_user_entity_label():
    import prompt

    cfg = _fake_cfg(
        user_address="你",
        raw_text="",
    )
    cfg.hint.return_value = "会记住你一切的女生"
    cfg.personality = "她会因为你熬夜而有点生气。"
    cfg.speech_patterns = "称呼用户：刚认识时用\"你\"。"
    cfg.backstory = "她不是 AI 助手，碰巧很在意你。"
    cfg.interests = ""
    cfg.emotional_reactions = ""
    cfg.relationship_stages = ""
    cfg.agent_behavior = ""

    with patch("prompt.get_config", return_value=cfg), \
         patch("prompt.resolve_user_entity_label", return_value="李垦"):
        system = prompt._build_agent_system_prompt(agent_mode="reactive")

    assert "You are Miru, 李垦's" in system
    assert "会记住李垦一切" in system
    assert "李垦熬夜" in system
    assert "在意李垦" in system
    assert "address them naturally as '你'" in system
    assert "Let warmth and care show through the way you listen" in system
    assert "character names" in system
    assert "I don't see an image" in system
    assert "李垦 的" not in system


def test_retired_care_prompt_builder_is_gone():
    import care_engine

    assert not hasattr(care_engine, "_build_care_system_prompt")
    assert not hasattr(care_engine, "build_care_snapshot_prompt")


def test_bundled_sora_persona_reaches_full_and_fast_chat(monkeypatch):
    from pathlib import Path

    import character
    import prompt

    config = character.CharacterConfig()
    config._parse(Path(character.SOUL_PATH).read_text(encoding="utf-8"))
    monkeypatch.setattr(prompt, "get_config", lambda: config)
    monkeypatch.setattr(prompt, "resolve_user_entity_label", lambda: "Sam")
    assert config.name == "Sora" and config.user_address == "you"
    assert config.hint("memory_bank_name") == "Sora's memory"
    for stage in ("刚认识 / Just Met", "熟悉之后 / Growing Familiar", "很亲近 / Very Close"):
        assert stage in config.relationship_stages

    full = prompt._build_agent_system_prompt("proactive")
    fast = prompt.build_fast_local_chat_messages([], "Hi.")[0]["content"]
    for system in (full, fast):
        assert "You are Sora" in system
        assert "lightly flirty" in system
        assert "be clear that you are an AI companion" in system
        assert "keep affection pressure-free" in system
        assert "only claim completed actions when a tool result confirms them" in system
    assert "You cannot access the camera, screen, or microphone" in fast
    assert "Follow the brief in Sora's voice" in full
    assert "active companion's voice" in prompt.build_proactive_agent_user_message({})


def test_proactive_prompt_keeps_custom_name_and_address(monkeypatch):
    from character import CharacterConfig
    import prompt

    config = CharacterConfig()
    config._parse("# Identity\n- **Name**: Lumen\n- **User Address**: Captain\n\n# Personality\nQuiet and observant.")
    monkeypatch.setattr(prompt, "get_config", lambda: config)
    monkeypatch.setattr(prompt, "resolve_user_entity_label", lambda: "Sam")
    full = prompt._build_agent_system_prompt("proactive")
    fast = prompt.build_fast_local_chat_messages([], "Hi.")[0]["content"]
    for system in (full, fast):
        assert "You are Lumen" in system and "Captain" in system
        assert "Quiet and observant" in system
    assert "Follow the brief in Lumen's voice" in full
    assert "Follow the brief in Miru's voice" not in full
