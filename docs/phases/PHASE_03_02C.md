# Phase 3.2C — Provider Credential Binding and Owner API Regression

## 1. Verify the starting checkpoint
- Read CLAUDE.md and Phase 3 records.
- Check Git status. Starting HEAD is `bc8d464616a46a90c0a926e96a30d0b189c8d9f4`.

## 2. Use one connection resolver
- In `ai_config.py`, unified setup-time discovery, ping, and inference using consistent resolved endpoint and credential resolution (`_resolve_tier`).
- Removed independent shared-key fallback in `update_tier_config()`. Tiers with explicit host overrides use their own credentials exclusively.

## 3. Restore owner PATCH compatibility
- Preserved saved keys when clients send blank/omitted fields for shared/tier updates. Kept explicit key clearing via `clear_api_key: true`.
- Covered omitted, blank, and null fields consistently across `update_shared_config` and `update_tier_config`.

## 4. Verify model selection and URL persistence
- Preserved explicit model overrides.
- Bound automatic selections to effective connection and invalidated them when connection changes.
- Shared discovery (`update_shared_config`) updates only inheriting tiers (tiers without explicit host overrides).

## 5. Test and publish
- Ran shared-provider, AI configuration, and owner API test suites (50/50 tests passed successfully).
- Added regression test checking exact endpoint and key passed to discovery (`test_discovery_exact_endpoint_and_key`).
- Updated `docs/STATUS.md`, added `docs/phases/PHASE_03_02C.md`, and appended verification and session logs.
- Executed history prefix integrity and whitespace checks (`git diff --check`, `check_history_append_only.py`).
- Committed locally and pushed via fast-forward push to `origin/main` (`https://github.com/Emii31/Sora.git`). Verified matching local and remote hashes.
- Stopped after Phase 3.2C.