# Phase 4.5 — Offline Wake Phrase Detection

## Backend contract

- Authenticated `POST /api/voice/wake` accepts an `audio/wav` or `audio/x-wav` request body with 16 kHz mono PCM16 audio. Clips may be at most 3 seconds and 100,000 bytes.
- A successful response is `{"detected":true}` or `{"detected":false}`. Unavailable local recognition returns HTTP 503. Detection runs on demand and leaves chat history empty.
- Set `SORA_VOSK_MODEL_DIR` to an unpacked `vosk-model-small-en-us-0.15`. Its vocabulary lacks “Sora,” so the wake recognizer uses a restricted grammar with pronunciations for the name, similar phrases, and an unknown-words alternative. Push-to-talk continues using the full vocabulary. [Vosk grammar example](https://raw.githubusercontent.com/alphacep/vosk-api/master/python/example/test_words.py)
- Client microphone capture, continuous listening, and testing with real speakers and background noise remain pending.

## Claude Code handoff

The cumulative Phase 4.5 bundle is based on Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). In a clean Sora checkout, run `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. Publish to `origin/main` on Emii31/Sora using authenticated access. The next backend slice can cover camera input when explicitly requested. Keep the web, desktop, and Android client work for later.

## Verification

- Command: `SORA_TEST_VOICE_MODEL_DIR=/tmp/sora-45-model/vosk-model-small-en-us-0.15 SORA_TEST_PIPER_MODEL_PATH=/tmp/sora-44-model/en_US-ljspeech-medium.onnx PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q -rs --tb=line tests/test_voice_input.py tests/test_local_single_device_mode.py tests/test_chat_error_copy.py`. Exit 0, 67 passed and one optional Ollama voice-turn test skipped.
- The authenticated Flask route accepted a synthetic “Hey Sora” recording and rejected “Hey Sarah,” “Hey sorry,” “Hello there,” longer phrases containing the wake phrase, and silence. Additional standalone pronunciation probes succeeded for two eSpeak voice variants. Live microphone recordings and false-trigger rates remain unmeasured.
