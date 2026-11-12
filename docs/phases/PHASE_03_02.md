# Phase 3.2 — Shared Provider Configuration and Automatic Model Selection

- **Status**: Verified & Implemented
- **Starting Checkpoint**: c239cb13f678f8b548b2611e7215f9b9409893d5 -> new checkpoint after commit

## Summary of Work
1. **Shared Provider Connection (`ai_config.py`)**:
   - Added top-level `shared` configuration schema (`host`, `api_key`) in `ai_config.json`.
   - Documented and implemented resolution order: Tier Override (per-tier explicit host/key) → Shared Provider (`shared` endpoint and credential resolved together) → Environment Variables → Defaults.
   - Preserved existing per-tier configuration files, endpoints, explicit overrides, secret masking, and loopback HTTP/remote HTTPS behavior.
2. **Automatic Model Discovery & Selection (`ai_config.py`)**:
   - Implemented `discover_provider_models()` querying OpenAI-compatible `/models` endpoints.
   - Automatically selected suitable text models for chat and memory tiers, and vision models (when image support is confirmed) for the vision tier.
   - Maintained explicit model overrides and handled discovery failures gracefully.
   - Kept discovery out of per-message paths and ensured cache invalidation on connection updates (`invalidate_cache()`).
3. **API Endpoints (`admin_api.py`, `app.py`)**:
   - Added PATCH routes (`/api/admin/ai-config/shared`, `/api/owner/ai-config/shared`) for updating shared provider configurations under administrative and owner authentication.
4. **Testing (`tests/test_shared_provider.py`)**:
   - Added robust unit test coverage verifying shared provider resolution, precedence rules, public config masking, and automatic model selection with mocked provider responses (all 38 tests passed successfully).
5. **Live Benchmark Status Note**:
   - Recorded that Phase 3.1B benchmark runner imports auth before setting disposable `DATA_DIR` and reuses history across turns; live benchmark runner timings remain pending.
