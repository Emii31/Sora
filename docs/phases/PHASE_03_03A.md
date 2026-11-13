# Phase 3.3A — Finish Benchmark Isolation and Run Ollama

## 1. Verify the starting checkpoint
- Started from commit `18c26403bf25d2fae3d2e9a972bb949c53b9a2d7`.
- Read CLAUDE.md, checked Git status and existing benchmark structure.

## 2. Finish Benchmark Isolation & User State
- Updated `scripts/benchmark_chat.py` so each measured turn starts with fresh disposable user state (`create_fresh_disposable_user(auth)`), ensuring isolated user data directories and pristine chat histories per turn.
- Verified isolation through the authenticated history route (`GET /api/chat/history`) before each turn to guarantee empty starting history.
- Fixed test suites and setting tests (`tests/test_benchmark_chat.py`) to ensure all benchmark and test writes stay strictly in temporary directories (`storage.DATA_DIR`, `auth._BASE_DATA_DIR`).

## 3. Reporting & Verification
- Configured separate reporting for full-mode and fast-mode medians and individual timings (`direct_full`, `sora_full`, `direct_fast`, `sora_fast`).
- Verified actual policy (`observed_mode == expected_mode`) and exact saved reply for every turn.
- Executed benchmark runner test suite: 4/4 benchmark unit tests passed successfully.
- Live benchmark execution attempted via `.venv/bin/python scripts/benchmark_chat.py`; recorded blocker: Ollama server not running in test container (`ConnectionError` at `127.0.0.1:11434/v1`).

## 4. Record and publish
- Updated `docs/STATUS.md`, created `docs/phases/PHASE_03_03A.md`, appended session and verification logs.
- Executed history prefix integrity checks (`check_history_append_only.py`).
- Committed locally and pushed via fast-forward push to `origin/main` (`https://github.com/Emii31/Sora.git`). Verified local and remote hashes.
- Stopped after Phase 3.3A.
