# Phase 6.3 — Protected shared memory over private Wi-Fi

Added a backend launcher at `scripts/serve_private_pairing.py`. One Flask application serves the same account store through two specific listeners. Owner controls stay on laptop loopback. The Wi-Fi listener requires TLS and a private IPv4 address, and exposes only health, pairing redemption and the paired-phone chat and memory routes. It rejects owner credentials on those protected Wi-Fi routes. This launcher is opt-in with `SORA_LOCAL_PAIRING=1` and requires a certificate and key.

## Physical Motorola result

- The phone reached the laptop directly over Wi-Fi. The laptop saw the Motorola's Wi-Fi address, and USB reverse forwarding was absent. USB issued test commands and transferred the disposable trust anchor.
- Android verified the HTTPS certificate using a supplied local trust anchor. It rejected the untrusted certificate, a hostname mismatch and a plaintext request to the TLS port. No system trust-store changes were made.
- The phone redeemed a single-use code, wrote the shared note, and sent the plant name in chat. Local Qwen on the laptop recalled **Juniper** after the laptop backend and phone test client restarted. Both devices could still read the exact note, and the account's persisted chat held four messages.
- The Wi-Fi listener did not expose the app shell or owner model settings. Revoking the phone returned HTTP 401 on its next history read. The laptop account still worked.
- The first network attempt used an ephemeral port and timed out. The laptop's UFW log identified the Motorola's incoming TCP requests as blocked. The successful short-lived test used a free port in an existing allow range, restricted its test listener to the Motorola's Wi-Fi address and changed no firewall rules. The listener and temporary phone files were removed, and the port was free again.

The test used a disposable account and test certificate. Ordinary Android app pairing, persistent certificate trust, credential storage and a dedicated deployment port remain open. Shared access still requires the laptop backend to be reachable.

## Verification

- From `/mnt/data/Companion/recovery/phase_06_03`, ran `source ../phase_04_59/env.sh && /mnt/data/Companion/Miru/.venv/bin/python -B -u wifi_replay.py LAPTOP_WIFI_IP MOTOROLA_WIFI_IP` with the two current private addresses. The first attempt exited 1 after the firewall timeout. After adjusting the test port and peer guard, the final run exited 0. See the [physical Wi-Fi results](../verification/phase_06_03/physical-wifi.json).
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_private_pairing_listener.py tests/test_device_pairing.py tests/test_shared_memory_backend.py tests/test_local_single_device_mode.py tests/test_invitation_direct_login.py tests/test_invitation_encoding.py tests/test_core_memory_limits.py tests/test_device_dedupe.py tests/test_chat_device_id.py tests/test_mobile_notification_memory_ui.py tests/test_owner_ai_config.py`. 112 passed, exit 0.
- The focused tests check address binding validation, Wi-Fi route scope, and the credential boundary between the two listeners.
