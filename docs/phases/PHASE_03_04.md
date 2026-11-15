# Phase 3.4 — Diagnose Local Chat Latency

## Starting checkpoint

- Baseline: `e69d08b67dd35e76d0457821e0b041e82a4cbf84`.
- The workstation's project volume was unavailable. Work ran in a temporary checkout of `Emii31/Sora` and a Python 3.11.18 virtual environment created from `requirements.txt`.

## Timing design

- Run `PYTHONDONTWRITEBYTECODE=1 MIRU_CLIENT_CONFIG_PATH=/tmp/sora-phase-34-unused-launcher.json /tmp/sora-phase-34-venv/bin/python -B -u scripts/benchmark_chat.py --timing` in the temporary checkout. In the regular checkout, use `.venv/bin/python -u scripts/benchmark_chat.py --timing`.
- The benchmark completes an untimed Ollama warm-up, uses identical synthetic prompts with fresh disposable users, and alternates full-first and fast-first pairs. Its raw console includes existing application logs. New `TIMING` records contain only a synthetic turn ID, policy, elapsed times, and model attempt outcomes.
- The benchmark registers one disposable user before sending chat and validates the trace against the actual request's message ID and saved assistant reply. It measures the Flask POST, queue and debounce, context assembly, preflight, history and tool preparation, agent, reply write, and history detection.
- The preflight and agent spans include their model attempts and any retry waits. These nested timings must not be added a second time. Model attempt counts reflect Sora's retry wrapper. SDK-internal retries and Ollama queueing, prompt evaluation, and decoding are included in the attempt duration.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-phase-34-venv/bin/python -B -m pytest -p no:cacheprovider -q tests/test_benchmark_chat.py tests/test_chat_preflight_routing.py tests/test_chat_error_copy.py tests/test_agent_modes_attention.py` — exit 0, 38 passed.
- The benchmark integration test exercises both mode orders through the real worker with mocked model calls. The retry test verifies a failed attempt, the backoff span, and the successful retry. Unrelated users and message IDs are excluded.

## Live run

Ollama 0.40.16 ran locally on the i5-7300U CPU with `qwen2.5:1.5b-instruct` and a 4,096-token context. The explicit warm-up completed before the first pair.

| Turn | Mode | Direct Ollama | Send to history | Queue wait | Context assembly | Preflight | Chat agent | Sora model attempts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Full | 8.95 s | 343.75 s | 1.50 s | 0.20 s | 34.59 s | 307.19 s | 1 retrieval, 1 agent |
| 2 | Fast | 58.06 s | 441.78 s | 1.50 s | 0.40 s | Skipped | 439.79 s | 2 agent, first timed out |

| 3 | Fast | 125.42 s | 238.20 s | 1.50 s | 0.39 s | Skipped | 236.15 s | 1 agent |

| 4 | Full | 103.11 s | 331.95 s | 1.50 s | 0.20 s | 89.97 s | 240.11 s | 1 retrieval, 1 agent |

All four turns passed, verified by their recorded worker policy and saved reply ID. The live command exited 0. The full-mode send-to-history median was **337.85 s** and the fast-mode median was **339.99 s**. Direct Ollama medians were **56.03 s** (full-mode turns) and **91.74 s** (fast-mode turns). All four queue waits were about 1.50 s. POST handling was under 0.07 s, successful reply writes took under 1 ms, and history detection took 0.08–0.17 s. The main chat agent took 240.11–307.19 s in full mode and 236.15–439.79 s in fast mode. With two turns per mode and concurrent background work, use these results for diagnosis, not as a stable speed estimate.

## Claude Code handoff

The app run logged the same 22,126-character system prompt in both modes. Ollama logged main chat inputs in excess of the available context and 120-second HTTP timeouts. The first fast turn's initial SDK call exhausted its transport attempts after 361.66 s, then Sora waited 2.44 s and made a second SDK call that succeeded in 75.67 s. Background memory processing also ran during the comparison, so wall-clock durations include possible contention.

Resume from the Phase 3.4 commit. The project volume was unavailable, the temporary checkout had no HTTPS push credentials, and the connected GitHub integration returned HTTP 403. An incremental Git bundle preserves the commit and these records. From a clean, authenticated Sora checkout at the Phase 3.3B baseline, fetch the bundle's `main` and merge `FETCH_HEAD` with `--ff-only`, then push to `origin/main`. The temporary benchmark environment and its raw log are not needed to resume.

The next change to test is a compact prompt and explicit output-token cap for the opt-in loopback fast text path. Retain the configured persona, bounded recent turns, current user message, reply delivery, and history behavior. Compare the new path against this baseline on the same model. Leave full mode as the default.
