# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 3.2A — Shared Provider Credential and Model Selection Fixes (Completed & Verified)
- **Current Status**: Bound credentials securely to their provider (host-only updates clear old keys to prevent cross-provider key leakage); preserved shared inheritance after connection tests (`ping_tier` testing an inheriting tier does not create unwanted tier overrides); implemented capability-based model selection (`_discover_and_select_model` verifying text/vision capability evidence and keeping discovery out of config reads/chat requests); added comprehensive unit tests (`tests/test_shared_provider.py` and updated `tests/test_ai_config.py`). Note: Live benchmark runner timings remain pending.
- **Next Action**: Stop after Phase 3.2A.
