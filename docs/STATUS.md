# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 3.2 — Shared Provider Configuration and Automatic Model Selection (Completed & Verified)
- **Current Status**: Implemented shared opt-in provider configuration (`shared` endpoint and credential in `ai_config.json`), precise resolution precedence (Tier Override > Shared Provider > Environment > Default), automatic model discovery and selection (`discover_provider_models`), secret masking, admin/owner patch endpoints (`/api/admin/ai-config/shared`, `/api/owner/ai-config/shared`), and comprehensive test coverage (`tests/test_shared_provider.py`). Note: Phase 3.1B benchmark runner imports auth before setting disposable DATA_DIR and reuses history across turns; live benchmark runner timings remain pending.
- **Next Action**: Stop after Phase 3.2.
