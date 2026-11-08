import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_windows_capture_recovery_frontend import _function_source


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("platform,device", [
    ("linux", "Linux PC"), ("windows", "Windows PC"),
    ("macos", "Mac"), ("android", "phone"),
])
@pytest.mark.parametrize("mode", ["local", "remote"])
def test_settings_copy_matches_device_and_storage_scope(platform, device, mode):
    html = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
    functions = "\n".join(_function_source(html, name) for name in (
        "settingsRenderAiPanel", "settingsRenderSystemPanel",
        "_loadSettingsInvitationCode", "settingsSwitchAccount",
    ))
    fixture = json.dumps({"platform": platform, "device": device, "mode": mode}, ensure_ascii=False)
    harness = "const fixture = " + fixture + ";\n" + r"""
const assert = require('node:assert/strict');
const window = { __MIRU_DESKTOP_PLATFORM__: fixture.platform };
if (fixture.platform === 'android') window.MiruAndroid = {};
const elements = Object.fromEntries([
  'settingsPanelAi', 'settingsPanelSystem', 'settingsInvitationCode',
  'settingsInvitationHint', 'settingsCopyInvitationBtn',
].map(id => [id, { innerHTML: '', textContent: '' }]));
const document = { getElementById: id => elements[id] || null };
const localStorage = { getItem: () => null, removeItem: () => {} };
const navigator = { platform: fixture.platform };
const _clientModeMode = fixture.mode;
const _isMobile = fixture.platform === 'android';
const appConfigState = {};
const settingsAiConfigState = {};
const SETTINGS_AI_TIER_META = { vision: {}, chat: {}, memory: {} };
const _settingsAiTier = () => ({});
const _settingsAiStatusText = () => '';
const _settingsEsc = String;
const escapeHtml = String;
const _formatHotkeyDisplay = String;
const _updateAndroidCaptureUI = () => {};
const _loadScreenshotStats = () => {};
const fetch = async () => ({ ok: true, json: async () => (
  fixture.mode === 'local' ? { local_only: true } : { ok: true, invitation_code: 'fixture-code' }
) });
let confirmation;
const _confirm = async message => { confirmation = message; return false; };
""" + functions + r"""
(async () => {
  settingsRenderAiPanel();
  settingsRenderSystemPanel();
  await new Promise(resolve => setImmediate(resolve));
  await settingsSwitchAccount();
  const ai = elements.settingsPanelAi.innerHTML;
  const account = elements.settingsPanelSystem.innerHTML;
  const invitation = elements.settingsInvitationHint.textContent;
  if (fixture.mode === 'local') {
    assert.ok(ai.includes('These settings are saved on this ' + fixture.device), 'AI storage scope');
    assert.ok(account.includes('it will not delete the local Sora data on this ' + fixture.device), 'account description');
    assert.ok(invitation.includes('Sora is currently used only on this ' + fixture.device), 'local invitation hint');
    assert.ok(confirmation.includes('Local single-device data will remain on this ' + fixture.device), 'switch confirmation');
    if (fixture.platform === 'linux') {
      assert.ok(confirmation.includes('"Use only on this PC"'));
      for (const copy of [ai, account, invitation, confirmation]) assert.ok(!copy.includes('Mac'));
    }
  } else {
    assert.ok(ai.includes('on the Sora private server'));
    assert.ok(account.includes('the Sora data on the server will not be deleted'));
    assert.equal(elements.settingsInvitationCode.value, 'fixture-code');
    assert.ok(confirmation.includes('it will not delete chats, memories, or invitation codes on the server'));
  }
  console.log(JSON.stringify({ ok: true }));
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
"""
    result = subprocess.run(["node"], input=harness, capture_output=True,
                            text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True
