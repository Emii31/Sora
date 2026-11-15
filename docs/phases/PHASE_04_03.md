# Phase 4.3 — Verify a Complete Offline Voice Turn

## Starting checkpoint

- Local Phase 4.2 commit: `3b03e03a77b2e1dcde31782df99d895c9dd7a480`.
- Continued in the temporary Sora checkout. The cumulative bundle carries the handoff back to the regular checkout.

## End-to-end check

An opt-in integration test in `tests/test_voice_input.py` uses a fresh authenticated account. It sends an eSpeak-generated WAV to Vosk through `POST /api/voice/transcribe`, checks that chat history is still empty, and explicitly posts the transcript to `POST /api/chat`. It waits for the exact assistant reply in `GET /api/chat/history`, confirms the real worker used one successful `reactive_fast` model attempt, and passes the saved reply ID to `POST /api/voice/synthesize`. The Piper response must be playable WAV data containing non-silent PCM.

The final fixture sentence was “can you tell me a joke.” An earlier synthetic greeting was misrecognized and never reached chat. A single known fixture verifies the request chain. Recognition across voices and accents and device microphone and speaker behavior remain unverified.

## Reproduce

Install the optional dependencies and assets described in [Phase 4.1](PHASE_04_01.md) and [Phase 4.2](PHASE_04_02.md). Keep local Ollama running with the installed `qwen2.5:1.5b-instruct` model. This run used `OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1 ollama serve`. The test restricts Python socket lookups and connections to that endpoint. eSpeak NG and FFmpeg generate the synthetic input file in pytest's temporary directory.

```bash
SORA_TEST_VOICE_TURN=1 \
SORA_TEST_VOICE_MODEL_DIR=/absolute/path/to/the/vosk/model \
SORA_TEST_PIPER_MODEL_PATH=/absolute/path/to/the/piper/model.onnx \
PYTHONPATH=. .venv/bin/python -m pytest -q -rP \
  tests/test_voice_input.py::test_complete_offline_voice_turn
```

## Results

- Real end-to-end test exited 0 (1 passed). Observed times: Vosk transcription 1.48 s, Ollama chat to saved reply 12.63 s, and Piper synthesis 2.03 s. Total elapsed time was 16.14 s, producing 6.15 s of non-silent audio. The Ollama service started fresh and the test did not issue a warm-up.
- Separately, the voice endpoint, local single-device, and chat-error suites returned 50 passed with the full voice-turn test deselected. The individual Vosk and Piper smoke tests ran in that suite.
- Commands below record both successful runs. The shared options were `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-phase-34-venv/bin/python -B -m pytest -p no:cacheprovider` with the local model paths in `SORA_TEST_VOICE_MODEL_DIR` and `SORA_TEST_PIPER_MODEL_PATH`.
  - Live chain: set `SORA_TEST_VOICE_TURN=1` and use `-q -rP tests/test_voice_input.py::test_complete_offline_voice_turn`.
  - Regression: use `-q tests/test_voice_input.py tests/test_local_single_device_mode.py tests/test_chat_error_copy.py -k 'not test_complete_offline_voice_turn'`.

## Claude Code handoff

Import the cumulative Phase 4.3 bundle into a clean Sora checkout with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. It includes the earlier unpublished phases. Publish the resulting commit to Emii31/Sora on `origin/main` using authenticated access. The next proposed backend milestone is testing pluggable local delivery styles for spoken replies. Device UI work remains deferred.
