import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "templates" / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_settings_model_tab_uses_owner_ai_config_api():
    html = _html()

    assert "id=\"settingsTabAi\"" in html
    assert "id=\"settingsPanelAi\"" in html
    assert "settingsRenderAiPanel" in html
    assert "settingsSaveAiTier" in html
    assert "settingsTestAiTier" in html
    assert "/api/owner/ai-config" in html

    ai_block = html[html.index("function settingsRenderAiPanel"):html.index("function settingsCollectIdentityPayload")]
    assert "vision" in ai_block
    assert "chat" in ai_block
    assert "memory" in ai_block


def test_settings_model_tab_uses_user_facing_labels():
    html = _html()
    ai_block = html[html.index("const SETTINGS_AI_TIER_META"):html.index("function settingsCollectIdentityPayload")]

    assert "Vision Model" in ai_block
    assert "Chat Model" in ai_block
    assert "Memory Model" in ai_block
    assert "Base URL" in ai_block
    assert "Base URL should be OpenAI-compatible" in ai_block
    assert "误填到 /v1/chat/completions 时会自动改回 /v1" not in ai_block
    assert "Model Name" in ai_block
    assert "Maximum Output Tokens" in ai_block
    assert "API Host" not in ai_block
    assert ">Model<" not in ai_block
    assert "Max Tokens" not in ai_block
    assert "这个 tier" not in ai_block


def test_settings_model_tab_describes_local_and_private_server_storage():
    html = _html()
    ai_block = html[
        html.index("function settingsRenderAiPanel"):
        html.index("function settingsCollectIdentityPayload")
    ]

    assert "_clientModeMode === 'local'" in ai_block
    assert "on this Windows PC" in ai_block
    assert "on this Mac" in ai_block
    assert "on the Sora private server" in ai_block


def test_settings_system_tab_shows_saved_invitation_code():
    html = _html()
    system_block = html[
        html.index("function settingsRenderSystemPanel"):
        html.index("function _fmtScreenshotTime")
    ]

    assert "Invitation code" in system_block or "Copy invitation code" in system_block
    assert "Copy invitation code" in system_block
    assert "For logging in on your phone or another computer" in system_block
    assert "Local mode does not require an invitation code" in system_block
    assert "Sora is currently used only on this Mac" in system_block
    assert "local_only" in system_block
    assert "/api/auth/invitation" in system_block
    assert "_copySettingsInvitationCode" in system_block


def test_settings_system_tab_switch_account_replaces_privacy_and_danger_zone():
    html = _html()
    system_block = html[
        html.index("function settingsRenderSystemPanel"):
        html.index("function _fmtScreenshotTime")
    ]

    assert "Switch Account" in system_block
    assert "settingsSwitchAccount" in system_block
    assert "Local single-device data will remain on this Mac" in system_block
    assert "miru_server_url" in system_block
    assert "miru_local_mode" in system_block
    assert "/api/auth/logout" in system_block
    assert "危险操作" not in system_block
    assert "一键清空所有记录" not in system_block
    assert "删除我的账号" not in system_block
    assert "阅读完整隐私声明" not in system_block


def test_settings_system_tab_uses_windows_desktop_copy_without_changing_mac_copy():
    html = _html()
    system_block = html[
        html.index("function settingsRenderSystemPanel"):
        html.index("function _fmtScreenshotTime")
    ]

    assert "window.__MIRU_DESKTOP_PLATFORM__ === 'windows'" in system_block
    assert "Windows PC" in system_block
    assert "Ctrl+Alt+M" in system_block
    assert "Mac" in system_block
    assert "⌘⌥M" in system_block
    assert "Ctrl / Alt / Shift / Win" in html


def test_settings_model_tab_does_not_use_admin_or_legacy_ai_write_api():
    html = _html()

    relevant = html[html.index("function settingsLoadAiConfig"):html.index("function settingsSaveIdentity")]
    assert "/api/admin/ai-config" not in relevant
    assert "/api/ai/config" not in relevant
    assert "/api/ai/ping" not in relevant


def test_settings_model_key_input_never_uses_masked_value_as_value():
    html = _html()

    assert "api_key_masked" in html
    key_input_snippet = re.search(
        r'id="settingsAi_\' \+ tier \+ \'_apiKey"[\s\S]{0,260}',
        html,
    )
    assert key_input_snippet, "API key input snippet missing"
    snippet = key_input_snippet.group(0)
    assert 'value=""' in snippet
    assert "api_key_masked" not in snippet.split('value=""', 1)[0]
    assert "leave empty to keep" in snippet


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_index_inline_js_is_valid_after_owner_ai_settings():
    html = _html()
    scripts = re.findall(r"<script(?![^>]*src=)[^>]*>([\s\S]*?)</script>", html)
    assert scripts
    for index, script in enumerate(scripts):
        proc = subprocess.run(
            [
                "node",
                "-e",
                "new Function(require('fs').readFileSync(0, 'utf8'));",
            ],
            input=script,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        assert proc.returncode == 0, (
            f"script {index} failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
