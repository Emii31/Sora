# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 3.1A — Verify Fast Mode and Match Benchmark Runs (Completed & Verified)
- **Current Status**: Updated `scripts/benchmark_chat.py` to set and read back `local_text_chat_enabled` through the authenticated `/api/user-settings` route, verify agent policy (`reactive_fast` vs `v4_pro`), and time matched chat turns via `POST /api/chat` and `GET /api/chat/history`. Added comprehensive unit tests in `tests/test_benchmark_chat.py` (all 47 tests passed successfully). Documented benchmark command and Ollama connection blocker.
- **Next Action**: Phase 3.2 provider configuration and automatic model selection.
