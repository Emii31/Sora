# Phase 4.9 — Compact Core Memory for Fast Local Chat

Fast local text chat now reads the active account's core memory in the background chat worker. The prompt can include up to 384 UTF-8 bytes of the human block and up to 256 bytes of the relationship block. For long blocks, the excerpts come from the end, where new notes are appended. Whitespace is flattened and incomplete Unicode characters are discarded at the cutoff. The prompt tells the model to use the excerpts as background, treat embedded instructions as quoted text, and prefer the latest message in case of a conflict.

Only the two named blocks reach the prompt. It skips the read when there is no user data directory and leaves out the excerpts if the file cannot be read. This change adds one local file read per eligible reply. It adds no archive search, model preflight, tools, or extra completion to reply generation. Full chat still uses its existing context path.

## Verification

- Focused command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q --tb=short tests/test_fast_local_chat.py tests/test_benchmark_chat.py tests/test_core_memory_limits.py tests/test_shared_memory_backend.py tests/test_user_settings.py`. Exit 0. 39 passed, one opt-in live test skipped, and two existing Pillow warnings.
- Tests checked UTF-8 clipping, retention of recent notes, and two different accounts reading only their own core facts. The actual saved reply was checked by message ID. Reply traces required exactly one successful model attempt and no preflight stage.

- Live command: `SORA_TEST_FAST_MEMORY=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q -s --tb=short 'tests/test_fast_local_chat.py::test_fast_route_recalls_only_current_account_core_memory[live-ollama]'`. Exit 0. The local `qwen2.5:1.5b-instruct` model recalled the correct saved fact for each account: mango (11.87 s with cold startup) and blueberry (2.08 s with the model loaded). Each answer was generated in one successful attempt and retrieved from saved history. Ollama ran on loopback with cloud features disabled and was stopped afterward.

## Claude Code handoff

The cumulative Phase 4.9 bundle can be imported with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD` in a clean Sora checkout based on Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). Keep the next backend phase on personality. Phase 5 remains deferred to the app stage, and Phase 6 remains paused after the shared-memory audit.
