# Phase 4.1 — Offline Push-to-Talk Transcription Backend

## Starting checkpoint

- Local Phase 3.5 commit: `951d4b0d42e1133f903b18954a51b04a2fe07d7e`.
- The project volume is still unavailable. Work continued in the temporary Sora checkout and virtual environment.

## Endpoint

- `POST /api/voice/transcribe` uses the existing user authentication middleware. Submit a raw `audio/wav` body with 16 kHz, 16-bit mono PCM. Each request may contain up to 30 seconds and 1,000,000 bytes.
- The response is `{"text":"..."}`. Silence yields an empty string. The endpoint processes audio in memory and returns the transcript for review. Sending it to chat is a separate client action.
- The backend processes one clip at a time. Missing setup, an unavailable recognizer, and concurrent recognition return HTTP 503 with an actionable message. Invalid audio returns HTTP 400, an unsupported media type returns 415, and an oversized body returns 413.
- This checkpoint covers the backend request. Microphone capture and push-to-talk controls remain future client work. Voice output and wake-word detection are later steps.

## Optional setup

1. Install the recognizer in Sora's project virtual environment with `.venv/bin/python -m pip install -r requirements/voice.txt`.
2. Download and extract `vosk-model-small-en-us-0.15` from the [official Vosk model list](https://alphacephei.com/vosk/models). This is the English model used for verification. Keep the weights outside Git.
3. Set `SORA_VOSK_MODEL_DIR` to that extracted directory in the backend process environment before launching Sora. The runtime loads the explicit local path. Installing the package and downloading the model require network access once. Recognition makes no provider API request.
4. To verify the whole endpoint with synthetic audio, install `espeak-ng` and `ffmpeg` if they are missing and run `SORA_TEST_VOICE_MODEL_DIR=/absolute/path/to/the/model PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_input.py`.

## Verified

- `SORA_TEST_VOICE_MODEL_DIR=/tmp/sora-phase-41-model/vosk-model-small-en-us-0.15 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-phase-34-venv/bin/python -B -m pytest -p no:cacheprovider -q -rP tests/test_voice_input.py tests/test_local_single_device_mode.py tests/test_chat_error_copy.py` — exit 0, 41 passed.
- Through the Flask route, Vosk transcribed the synthetic sentence “the quick brown fox jumps over the lazy dog” exactly. The first call took 2.25 s including model load. An actual silence sample returned an empty transcript. The test ran in the sandbox with Python socket connections blocked. This verifies the backend and the model on synthetic US-English audio. Real microphone audio and accent accuracy are unmeasured.
- Model archive integrity check: `unzip -tq /tmp/sora-phase-41-vosk.zip` exited 0. Model weights and test audio are outside the repository.

## Claude Code handoff

Import the cumulative Phase 4.1 bundle into a clean Sora checkout using `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. It includes the unpublished Phase 3.4 and Phase 3.5 checkpoints as well. Publish using authenticated GitHub access to Emii31/Sora on `origin/main`. The next backend milestone is local speech synthesis for Sora's replies.
