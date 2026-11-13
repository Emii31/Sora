# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 3.2C — Provider Credential Binding and Owner API Regression (Completed & Verified)
- **Current Status**: Unified connection resolution across setup, discovery, ping, and inference (`_resolve_tier`); removed shared-key fallback for tier overrides; restored owner PATCH compatibility (preserving saved keys on blank/omitted updates while supporting explicit clearing); limited shared discovery to inheriting tiers; added regression testing for exact discovery endpoint/key passing (50/50 tests passed across `tests/test_owner_ai_config.py`, `tests/test_shared_provider.py`, and `tests/test_ai_config.py`).
- **Next Action**: Stop after Phase 3.2C.