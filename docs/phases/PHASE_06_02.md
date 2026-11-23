# Phase 6.2 — Private phone pairing and shared-memory replay

Resumed the Android and shared-memory backend track from Phase 6.1. The laptop remains the source of truth for its existing account. Both devices use the same Markdown and chat-history files under that account's data directory.

## Pairing

Set `SORA_LOCAL_PAIRING=1` on the backend to enable the pairing routes. The laptop issues a code through `POST /api/pairing/code` using the existing local account's bearer credential on loopback. The code expires in five minutes. Issuing another code invalidates the previous unused code for that account. Android exchanges the code once at `POST /api/pairing/redeem`. One transaction consumes the code and issues a separate phone credential for the same account.

The server stores only the code and phone credential digests in a private SQLite file. An owner can list paired devices and revoke each one individually through `GET /api/pairing/devices` and `DELETE /api/pairing/devices/<device_id>`. Paired bearer credentials are valid for chat and the designated memory routes. Owner settings, account management, and admin routes remain separate. Phone requests require HTTPS or direct loopback. Phase 6.2 verified loopback over USB. Private Wi-Fi, Android credential storage and pairing UI remain deployment work.

## Motorola and laptop verification

- The physical Motorola exchanged a code for its own bearer credential through a temporary USB reverse to laptop loopback. A second claim of the same code returned HTTP 401.
- The phone wrote a Markdown note and sent “My houseplant is named Juniper” to the real chat route. The laptop read the note from the same account.
- Stopped the first laptop backend process and started a separate process with the same disposable data directory. Fresh Android HTTP client processes loaded the phone credential from a temporary file. The phone and laptop still read the exact Markdown note. The laptop asked the real local Qwen route for the name and received “Juniper.” The recall came from saved chat context. The separate Markdown check establishes durable shared note storage.
- A phone request for owner model configuration returned HTTP 403. Revocation returned HTTP 204. The next phone history request returned HTTP 401, and the laptop owner credential still worked.
- The run used synthetic data, no Android app changes and no physical device reboot. Removed the disposable data, temporary device credential and reverse connection. The backend listened on localhost throughout.

## Reproduction and checks

- From `/mnt/data/Companion/recovery/phase_06_02`, ran `source ../phase_04_59/env.sh && /mnt/data/Companion/Miru/.venv/bin/python -B -u physical_replay.py`, exit 0. [Physical test evidence](../verification/phase_06_02/physical-shared-memory.json)
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_device_pairing.py tests/test_shared_memory_backend.py tests/test_local_single_device_mode.py tests/test_invitation_direct_login.py tests/test_invitation_encoding.py tests/test_core_memory_limits.py tests/test_device_dedupe.py tests/test_chat_device_id.py tests/test_mobile_notification_memory_ui.py tests/test_owner_ai_config.py`, 106 passed, exit 0.
- The tests cover code expiry, concurrent redemption, account ownership, transport checks, device scope and independent revocation. Existing invitation and owner credential behavior remains covered.

Next, verify protected private Wi-Fi access to the laptop backend from the Motorola. Shared access depends on the laptop backend being reachable. Offline edits and merging phone-local data are outside this deployment path.
