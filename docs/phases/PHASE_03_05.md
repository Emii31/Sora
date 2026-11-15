# Phase 3.5 — Compact Fast Local Chat

## Starting checkpoint

- Phase 3.4 commit: `b4914fe07df706dbc3baee002edd95407576c03e`.
- Continued in the temporary Sora checkout while the project volume and authenticated push remain unavailable.

## Behavior

- Opt-in loopback text chat builds a compact prompt from the configured character name, form of address, role, personality, and speech style. It keeps at most five recent text messages, clips each to 240 UTF-8 bytes, and preserves the current user message in full.
- Text over 2,048 UTF-8 bytes, current image attachments, remote providers, and the default opt-out continue through full chat. Fast mode skips full context assembly, archived-memory preflight, and tool construction. Normal reply completion and persistence use the existing chat worker.
- Fast mode sends one model request, caps output at 96 tokens or the owner's lower configured limit, and disables SDK retries for that request. It retains the existing provider timeout. An early 45-second trial saved one reply but timed out on the second, so the final implementation leaves the 120-second provider timeout in place.
- The fast path checks the resolved SDK client is still loopback before sending fast-mode content.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-phase-34-venv/bin/python -B -m pytest -p no:cacheprovider -q tests/test_fast_local_chat.py tests/test_benchmark_chat.py tests/test_chat_preflight_routing.py tests/test_chat_error_copy.py tests/test_agent_modes_attention.py tests/test_user_settings.py` — exit 0, 61 passed, two existing Pillow deprecation warnings.
- Tests cover persona and UTF-8 input bounds, current text preservation, owner caps, one attempt on timeout, loopback enforcement, mode routing, and saved replies through the actual worker with mocked inference.
- Live command: `PYTHONDONTWRITEBYTECODE=1 MIRU_CLIENT_CONFIG_PATH=/tmp/sora-phase-34-unused-launcher.json /tmp/sora-phase-34-venv/bin/python -B -u scripts/benchmark_chat.py --timing --fast-only`. In the regular checkout, use `.venv/bin/python -u scripts/benchmark_chat.py --timing --fast-only`.

## Live results

Ollama 0.40.16 ran the previously installed `qwen2.5:1.5b-instruct` on the i5-7300U CPU with cloud features disabled. Both synthetic turns used fresh users and the same prompt as Phase 3.4. The final command exited 0.

| Fast turn | Direct Ollama | Send to history | Worker model call | Attempts |
| --- | ---: | ---: | ---: | ---: |
| 1 | 10.42 s | 3.18 s | 1.48 s | 1 |
| 2 | 11.04 s | 3.06 s | 1.34 s | 1 |
| Median | 10.73 s | 3.12 s | 1.41 s | 1 |

The 1.50 s debounce was the largest remaining stage in these two turns. The Phase 3.4 fast-mode send-to-history median was 339.99 s, with provider timeouts and background work. These two samples are a live smoke comparison against that historical run. Full mode was verified in tests and its live timings were not remeasured for this phase.

## Claude Code handoff

The cumulative Phase 3.5 Git bundle includes both Phases 3.4 and 3.5. Fetch its `main` into a clean Sora checkout, fast-forward with `git merge --ff-only FETCH_HEAD`, and publish using the authenticated `origin` for Emii31/Sora. One cumulative import is sufficient. GitHub write access remains pending, so the current temporary checkout and its raw log are optional.
