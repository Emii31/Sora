# Phase 3.3B — Measure Live Local Chat

## 1. Verify the starting checkpoint
- Started from commit `5dd707a0084833bf6c0d6c0bb247c23b485ed9f1`.
- Read CLAUDE.md, checked Git status and Ollama availability (`ollama list` confirmed `qwen2.5:1.5b-instruct` installed and active).

## 2. Execute Live Benchmark Run
- Executed `.venv/bin/python scripts/benchmark_chat.py` under matched conditions (identical prompt, disposable user state per turn, alternating execution order across pairs).
- Verified both Full Mode (`v4_pro`) and Fast Mode (`reactive_fast`) completed successfully with correct policies and exact saved replies verified via `/api/chat/history`.

## 3. Measured Timings & Medians
- **Full Mode Direct Latency**: Individual: `[5.54s, 106.90s]` | Median: `56.22s` (first request was warm; subsequent request experienced concurrent background sleep agent load).
- **Full Mode Sora Send-to-History Latency**: Individual: `[39.45s, 450.80s]` | Median: `245.12s`.
- **Fast Mode Direct Latency**: Individual: `[97.83s, 128.39s]` | Median: `113.11s`.
- **Fast Mode Sora Send-to-History Latency**: Individual: `[55.21s, 120.39s]` | Median: `87.80s`.
- **Overall Success**: True (4/4 benchmark turns passed successfully).

## 4. Record and publish
- Updated `docs/STATUS.md`, created `docs/phases/PHASE_03_03B.md`, appended session and verification logs.
- Executed history prefix integrity checks (`check_history_append_only.py`).
- Committed locally and pushed via fast-forward push to `origin/main` (`https://github.com/Emii31/Sora.git`). Verified local and remote hashes.
- Stopped after Phase 3.3B.
