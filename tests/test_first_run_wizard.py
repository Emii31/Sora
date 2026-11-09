import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LOGIN_HTML = ROOT / "templates" / "login.html"


def test_first_run_wizard_exposes_expected_paths():
    html = LOGIN_HTML.read_text(encoding="utf-8")

    assert "Where should Sora live?" in html
    assert "This computer only" in html
    assert "Keep Sora on this computer" in html
    assert "Local single-device mode" not in html
    assert "Suitable for trying Sora first" not in html
    assert "Start Local Use" in html
    assert "/api/client/local/start" in html
    assert "view-api-setup" in html
    assert "API Key" in html
    assert "Connect Sora's models" not in html
    assert "Configure API Key first" not in html
    assert "Sora needs three sets of models: vision, chat, and memory" in html
    assert "Enter OpenAI-compatible Base URL for service address" in html
    assert "Automatically corrected to /v1 when entered as /v1/chat/completions" not in html
    assert 'body[data-view="api-setup"] .sub' in html
    assert 'body[data-view="api-setup"] .note' in html
    assert "apiVisionHost" in html
    assert "apiChatHost" in html
    assert "apiMemoryHost" in html
    assert "saveApiSetupAndEnter" in html
    assert "skipApiSetupAndEnter" not in html
    assert "apiSetupSkipBtn" not in html
    assert "暂时跳过" not in html
    assert "可以先跳过" not in html
    assert "completeClientSetup" in html
    assert "/api/client/setup/complete" in html
    assert "/api/owner/ai-config/' + encodeURIComponent(tier) + '/test" in html
    assert "Model configuration saved and tested successfully, entering Sora." in html
    assert "Please complete all three sets (Vision, Chat, Memory) and test before entering Sora." in html
    assert "u.searchParams.set('api_setup', status)" in html
    assert "enterMiruFromApiSetup('configured')" in html
    assert "enterMiruFromApiSetup('skipped')" not in html
    assert "if (!payloads.length)" not in html
    assert "resumePendingApiSetup" in html
    assert "setup_complete !== false" in html
    assert "miru_api_setup_skipped" not in html
    assert "No invite code needed" in html
    assert "without multi-device sync" in html
    assert "Multi-device sync" in html
    assert "I have an invite code" in html
    assert "I do not have an invite code" in html
    assert "Official Server" in html
    assert "Self-hosted server" in html
    assert "/api/client/provision/self-server/create" in html
    assert "/api/client/provision/self-server/status/" in html
    assert "/api/auth/login" in html
    assert "pollInFlight" in html
    assert "resetSelfProgress" in html
    assert "sakura-spinner" in html
    assert "deploy-steps" in html
    assert "Sora Service Package" in html
    assert "selfImageTar" in html
    assert "FormData" in html
    assert "Uploading service package to server" in html
    assert "selfSuccess" in html
    assert "Copy Invite Code" in html
    assert "Enter Sora" in html
    assert "Create another Sora" not in html
    assert "Re-check public access" in html
    assert "/api/client/provision/self-server/public-health/" in html
    assert "first available port" in html
    assert "pollFailures" in html
    assert "selfRetryJobId" in html
    assert "selfHealthRetryJobId" in html
    assert "do not recreate" in html
    assert "Re-check status" in html
    assert "e.status === 404" in html
    assert "Creation task interrupted" in html
    assert "Auto-login" not in html
    assert "sora/server:0.2.0" in html
    assert "sora/server:0.1.0" not in html
    assert "ccr.ccs.tencentyun.com/contextlife/miru-server" not in html
    assert "Initial connection will trust this server's fingerprint" in html
    assert "Please enter SSH username matching server login" in html
    assert "Select SSH Private Key" in html
    assert "enter <code>//</code> in the password field" in html
    assert "passwordless sudo" in html
    assert "system administrator" in html
    assert "SSH User" in html
    assert "ssh_user: valueOf('selfUser')" in html
    assert "ssh_user: valueOf('selfUser') || 'ubuntu'" not in html
    assert "ssh_user: valueOf('selfUser') || 'root'" not in html
    assert 'value="ubuntu"' not in html
    assert "Cloud server root password" not in html
    assert "e.g. ubuntu" not in html
    assert 'placeholder="Enter your cloud server public IPv4"' in html
    assert 'placeholder="203.0.113.10"' not in html
    assert "Directly encoded server" not in html
    assert "Standalone Sora instance" not in html
    assert "Sora Server image package" not in html
    assert "Host Directory" not in html
    assert "Instance Start Port" not in html
    assert "Instance End Port" not in html
    assert "Deployment script" not in html
    assert "discovery" not in html
    assert "Local single-device mode will be available in future versions" not in html


def test_first_run_creation_paths_offer_api_setup_before_entering_app():
    html = LOGIN_HTML.read_text(encoding="utf-8")

    local_body = re.search(
        r"window\.startLocalMode = async function\(\) \{([\s\S]*?)  \};",
        html,
    )
    assert local_body, "startLocalMode missing"
    local_js = local_body.group(1)
    assert "if (!data.is_new)" in local_js
    assert (
        "window.location.href = withDesktopClientParams('/app?token=' + "
        "encodeURIComponent(data.token));"
    ) in local_js
    assert "beginApiSetup" in local_js

    enter_body = re.search(
        r"window\.enterSelfServer = async function\(\) \{([\s\S]*?)  \};",
        html,
    )
    assert enter_body, "enterSelfServer missing"
    assert "returnState: true" in enter_body.group(1)
    assert "setupComplete: false" in enter_body.group(1)
    assert "beginApiSetup" in enter_body.group(1)


def test_first_run_wizard_does_not_restore_legacy_discovery_login():
    html = LOGIN_HTML.read_text(encoding="utf-8")

    assert "mirulife.top" not in html
    assert "DISCOVERY_URL" not in html
    assert "DEFAULT_SERVER_URL" not in html
    assert "旧的 discovery 逻辑" not in html
    assert "MIRU-ABCDEF" not in html
    assert "Milestone" not in html
    assert "Invalid invite code format, please check your copy" in html


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_first_run_wizard_inline_js_is_valid():
    html = LOGIN_HTML.read_text(encoding="utf-8")
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
            timeout=10,
        )
        assert proc.returncode == 0, (
            f"script {index} failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
