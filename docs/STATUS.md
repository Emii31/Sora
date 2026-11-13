# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 3.2B — Keep Provider Credentials and Model Selections Together (Completed & Verified)
- **Current Status**: Bound automatic model selections to their connection: discovered model IDs are tracked separately from explicit overrides (`auto_model`/`auto_model_host`), invalidated when the endpoint or credential changes, and re-discovered only at setup time. Discovery stays out of config reads and chat requests. Omitted, blank, and null credentials are treated consistently. Verified with mocked clients that no request carries a credential belonging to a different endpoint (43 tests passed across tests/test_ai_config.py and tests/test_shared_provider.py).
- **Next Action**: Stop after Phase 3.2B.