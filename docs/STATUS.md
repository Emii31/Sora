# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 3.2D — Prevent Credential Reuse After an Endpoint Change (Completed & Verified)
- **Current Status**: Implemented effective API base URL endpoint comparison (`_is_same_endpoint`) in `ai_config.py` before provider operations; endpoint changes without a replacement key now clear saved credentials to prevent post-change reuse, while same-endpoint updates preserve credentials; invalidated automatic model selections upon connection changes; updated and verified test suites (52/52 tests passed across `tests/test_shared_provider.py`, `tests/test_ai_config.py`, and `tests/test_owner_ai_config.py`).
- **Next Action**: Stop after Phase 3.2D.
