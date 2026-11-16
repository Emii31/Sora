# Phase 4.8 — Personality and Voice Backend Review

## What the backend delivers

| Path | Current behavior |
| --- | --- |
| Character configuration | `character.py` selects the active character's `soul.md` or the bundled Sora persona. The configuration is cached per user. The bundled persona defines the name, conversational style, emotional reactions, and relationship stages. |
| Full chat | `prompt._build_agent_system_prompt()` includes the configured role, personality, speech patterns, emotional reactions, and relationship guidance. `core._build_chat_context()` adds core memory, the archival index, and other surrounding context. |
| Fast loopback chat | `prompt.build_fast_local_chat_messages()` includes the name, addressing style, short role and personality fields, speech style, and up to five recent messages. It skips the full prompt, model-based preflight, tools, and the core memory blocks. A remembered preference can therefore disappear from an ordinary conversation when fast mode is enabled. |
| Voice turn | Transcription returns text. The caller explicitly sends it to chat and can then synthesize the saved reply belonging to the authenticated account. No extra LLM call is needed to speak the reply. |
| Speech delivery | Piper uses one configured local model. The caller can request neutral, warm, or playful pacing, with neutral as the default. These presets change speed and pauses. They do not adapt automatically to Sora's emotional state, and the selected voice depends on the locally supplied model. |
| Wake phrase and camera | The backend can recognize a submitted wake clip and describe a submitted image. Microphone activation, on-demand camera capture, audio playback, and interruption belong to client integration. |

## Remaining Phase 4 backend work

1. **Phase 4.9 — Compact memory for fast chat.** Add a bounded excerpt from the active account's local human and relationship blocks to the fast prompt. Keep reply generation to one Ollama completion, without adding an archive lookup or model-based preflight. Verify the account scope, input size, and actual saved reply.
2. Review the bundled persona's remaining literal address and branding, and distinguish in-character conversation from claims about real-world capabilities. The bundled `soul.md` still contains a Chinese direct-address value, and the full proactive prompt includes an English sentence naming Miru directly. Preserve existing relationship-stage keys and configured characters. This review did not change persona text.
3. Verify the selected local voice by listening before claiming it matches the user's preferred sound. The current tests establish WAV generation and the pacing differences. The app can expose playback settings later. Automatic emotion-based delivery is a separate backend feature.

## Phase order and handoff

Phase 5 remains scheduled for the app stage. Phase 6.1 was an early architecture audit, and the shared-memory work is paused at that checkpoint. Finish the remaining Phase 4 backend work before resuming it. The cumulative Phase 4.8 bundle includes the Phase 6.1 audit in its history. To import it into a clean Sora checkout, use `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. The bundle requires commit `e69d08b67dd35e76d0457821e0b041e82a4cbf84`.

## Verification

- Command: `SORA_TEST_VOICE_TURN=1 SORA_TEST_VOICE_MODEL_DIR=/tmp/sora-45-model/vosk-model-small-en-us-0.15 SORA_TEST_PIPER_MODEL_PATH=/tmp/sora-44-model/en_US-ljspeech-medium.onnx PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q -rP --tb=short tests/test_voice_input.py tests/test_fast_local_chat.py tests/test_agent_modes_attention.py tests/test_care_engine_persona.py tests/test_core_memory_limits.py`. Exit 0, 73 passed.
- A generated recording passed through Vosk, the loopback `qwen2.5:1.5b-instruct` model, and Piper. Transcription took 0.92 s, send-to-saved-reply took 15.28 s, and synthesis took 2.84 s. Total time was 19.04 s, producing 5.91 s of non-silent audio. The reply trace confirmed one successful model attempt for reply generation in fast mode.
- With the same input, Piper produced 2.89 s neutral, 3.16 s warm, and 2.74 s playful. This verifies the timing changes. Subjective tone, microphone capture, playback, and conversations across multiple sessions remain untested.
- Ollama ran on loopback with cloud features disabled, using the existing cached model. The temporary server was stopped after verification. This phase changed project records only.
