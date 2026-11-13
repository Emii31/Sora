# Phase 3.2D — Prevent Credential Reuse After an Endpoint Change

## 1. Verify the starting checkpoint
- Started from commit `c4b9f4e9e9e6dff11463a9739b4b50a1a79fac74`.
- Read CLAUDE.md, checked Git status.

## 2. Fix shared and tier-specific updates in ai_config.py
- Implemented `_is_same_endpoint` using `_openai_base_url_from_host` to compare old and new effective API base URLs (preserving equivalent URL spellings and distinguishing different provider paths).
- For the same endpoint, omitted, blank, and null key fields preserve the saved credential.
- Kept `clear_api_key: true` as an explicit clear.
- For a different endpoint, require a nonblank replacement key or save connection with old key cleared (`api_key: ""`), preventing credential reuse after an endpoint change.
- Invalidate automatic model selections (`auto_model`, `auto_model_host`) when the connection changes.

## 3. Test exact behavior
- Updated `test_endpoint_change_clears_key_and_prevents_credential_reuse` in `tests/test_shared_provider.py` and `test_update_invalidates_cache_for_hot_reload` in `tests/test_ai_config.py`.
- Verified endpoint changes clear keys, same-endpoint blank updates preserve credentials, explicit clearing works, and replacement keys succeed.
- Ran test suites: 52/52 tests passed successfully across `tests/test_shared_provider.py`, `tests/test_ai_config.py`, and `tests/test_owner_ai_config.py`.

## 4. Record and publish
- Updated `docs/STATUS.md`, `docs/phases/PHASE_03_02D.md`, and appended session and verification logs.
- Executed history prefix integrity and whitespace checks (`git diff --check`, `check_history_append_only.py`).
- Committed locally and pushed via fast-forward push to `origin/main` (`https://github.com/Emii31/Sora.git`). Verified matching local and remote hashes.
- Stopped after Phase 3.2D.
