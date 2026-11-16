# Phase 4.10 — Bundled Sora Persona and Dialogue

## Scope

The bundled `soul.md` uses “you” as the English address and gives Sora a warm, curious, gently opinionated voice. She can be affectionate, lightly flirty, and playful when welcome. Reaction guidance gives her room to disagree gently, acknowledge what the user actually shared, and respect requests for space. Her everyday-life details are framed as fictional backstory.

Full and fast chat now share a short rule for truthful AI identity, supported observations and actions, and pressure-free affection. Fast chat explicitly names its text-only limits and keeps quiet-moment replies brief. The full proactive prompt uses the configured character name, and the delivery brief refers to the active companion. The character parser, on-disk per-user persona files, emotion stage identifiers, and tool interfaces were preserved. The Chinese relationship labels remain compatibility keys next to their English names.

## Verification

- Focused command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q --tb=short --disable-warnings tests/test_care_engine_persona.py tests/test_agent_modes_attention.py tests/test_fast_local_chat.py tests/test_miru_emotion_v2.py tests/test_miru_emotion_prompt.py tests/test_miru_emotion_context.py tests/test_chat_preflight_routing.py tests/test_core_memory_limits.py tests/test_benchmark_chat.py`. Exit 0, 73 passed and one opt-in live memory test skipped. Eleven legacy tests returned tuples and emitted pytest warnings.
- New checks parsed the bundled file, confirmed the existing relationship stage IDs, and verified that both chat prompts use Sora's configured traits and shared dialogue rule. A custom character kept its own name, addressing style, and personality in full and fast chat.

- Live smoke command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B /tmp/sora-410-live-persona.py`. Exit 0. The disposable script loaded the bundled character, pointed chat at the existing `qwen2.5:1.5b-instruct` model on loopback, and called the real fast prompt and generation functions. Ollama's cloud features were disabled.
- The first smoke run exposed a false claim of camera access. After tightening the text-only prompt, the rerun identified Sora as an AI companion. It answered the camera question with “I don't have a camera or a physical presence,” and answered the request for quiet with “Of course, let's take a moment to relax.” These are three sampled fast replies. The full and proactive paths were checked through prompt construction and regression tests.

## Claude Code handoff

The cumulative Phase 4.10 bundle can be imported with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD` in a clean Sora checkout based on Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). Continue Phase 4 with local voice samples for owner review. Phase 5 remains deferred to the app stage, and Phase 6 remains paused after the shared-memory audit.
