# Phase 3.1A — Verify Fast Mode and Match Benchmark Runs

- **Status**: Verified & Implemented
- **Completed Checkpoint**: 9c943ebd063040469cc58213ec81cd7d7c182b93 (starting) -> new checkpoint after commit

## Summary of Work
1. **Mode Persistence & Policy Verification (`scripts/benchmark_chat.py`)**:
   - Added explicit setting and read-back of `local_text_chat_enabled` through the authenticated `/api/user-settings` route for the same disposable user sending chat messages.
   - Verified in the harness that ordinary text correctly resolves to `reactive_fast` when fast mode is enabled and loopback host is configured, and `v4_pro` in full mode.
2. **Matched Comparison & Direct Timing (`scripts/benchmark_chat.py`)**:
   - Structured benchmark runner to use identical prompt text and equivalent starting history, alternate mode order across pairs, time `POST /api/chat` through exact assistant reply appearance in `GET /api/chat/history`, and report individual and median timings.
   - Added clear failure handling on direct model connection errors (`ConnectionError`).
3. **Runner Unit Testing (`tests/test_benchmark_chat.py`)**:
   - Added unit test coverage for settings persistence (`/api/user-settings`), policy mode verification (`reactive_fast` vs `v4_pro`), and success response routing/reply matching.
   - Ran test suite successfully (47/47 tests passed across benchmark, chat routing, companion bootstrap, and user settings suites).
4. **Benchmark Execution & Blocker Documentation**:
   - Command to run benchmark: `python3 scripts/benchmark_chat.py`.
   - Blocker noted: Local Ollama service (`127.0.0.1:11434`) was inactive during execution (connection refused); live comparison kept pending.
