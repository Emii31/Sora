# Phase 6.1 — Shared Memory Backend Audit

## Decision

Use the laptop as the source of truth for shared memory. Pair Android to the existing laptop account so it opens the same files and core blocks. Both clients need to reach the laptop over a private connection. An Android account created in its separate embedded backend uses its own storage. Merging independently created Android data and offline editing are outside this first shared-memory path.

## Existing data and request flow

| Component | Behavior |
| --- | --- |
| Account routing | `auth.py` resolves a valid user bearer credential to one user ID and sets the request data directory. `storage.get_data_dir()` checks that the requesting account remains active. The registry's device ID is used for device identity and presence, not as the memory account key. |
| Canonical storage | Within `DATA_DIR/users/<user_id>/`, the `memory/` directory contains Markdown and slot metadata, `core_memory.json` contains the main prompt's core blocks, and `chat_history.json` keeps chat history separately. |
| Shared reads and writes | The current memory, slot, and core-memory routes read that same directory for both clients. Some memory GETs return ETags. A same-account client can revalidate and pick up a change on its next fetch. |
| Client cache | The connected Android WebView navigates to the server app. Its runtime and desktop web use the existing server APIs. The web client uses IndexedDB for cached reads and revalidates them using HTTP. This is not an offline write synchronization mechanism. |
| Change notifications | An overwrite through `memory.write_file()` publishes a per-account `data_changed` event. The raw `append_to_file()` helper does not broadcast one. A client refetch works for both. |
| Concurrent edits | Memory writes use a process-local lock. The overwrite API does not check a client-supplied revision, and a later full overwrite can replace an earlier one. A single backend process avoids adding a cross-process writer coordination problem. |

## Pairing and transport gaps

- Existing invitation login is reusable for the same account and returns its account token. A local single-device account has no invitation. Creating a separate invited account would open a different user directory.
- The inherited phone QR flow embeds the reusable account bearer credential in a URL and returns it in JSON. Removing a row from the device registry does not revoke the credential. These paths are unsuitable as the new private pairing flow.
- The development smoke launcher binds to loopback, which a physical Android phone cannot reach. The normal application entrypoint binds to all interfaces and can start a public tunnel. The Android project currently permits cleartext connections. The shared-memory deployment needs an explicit private listener and protected transport before using real data. Keep the public tunnel off.
- Android needs a way to pair with the existing laptop account, including a new phone credential that can be revoked independently. The first shared-memory deployment can use one connection to the laptop and the current data routes. No replication API or memory migration is needed for that path.

## Verification

Two independent Flask clients used the real authentication and memory routes with temporary data. The invited-account case used two sign-ins with the same invitation. The existing-local case supplied the laptop account credential directly to the simulated phone, solely to verify shared storage. A third account and an unauthenticated phone request were checked for isolation. Neither test establishes pairing, on-device behavior, or real network connectivity.

The laptop wrote Markdown, Android read it and appended to it, and the laptop received the new contents and a new ETag. Both clients saw the same core block and backed slot content. The neighboring account could not read either private record. The test checked that the Markdown contents matched the single file under the laptop account. Application code was unchanged.

## Claude Code handoff

Import the cumulative Phase 6.1 bundle with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD` on a clean Sora checkout. The bundle requires Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). Continue with Phase 6.2: design and implement expiring, single-use pairing to the existing laptop account, with independently revocable phone credentials and explicit permitted routes. Keep LAN listener changes and Android UI for their own verification steps. Preserve the laptop's account ID and data paths.

- Focused regression command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q --tb=short tests/test_shared_memory_backend.py tests/test_local_single_device_mode.py tests/test_invitation_direct_login.py tests/test_invitation_encoding.py tests/test_core_memory_limits.py tests/test_device_dedupe.py tests/test_chat_device_id.py tests/test_mobile_notification_memory_ui.py`. Exit 0, 97 passed.
