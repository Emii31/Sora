# Phase 4.2 — Offline Speech Synthesis for Saved Replies

## Starting checkpoint

- Local Phase 4.1 commit: `4ce189c7981fbed0f5600975f73bf912ca811fd4`.
- Continued in the temporary Sora checkout and virtual environment.

## Endpoint

- `POST /api/voice/synthesize` accepts `{"message_id":"<saved assistant reply ID>"}` and returns a WAV body. The existing user authentication middleware scopes the lookup to the caller. The reply must be one of the latest 200 chat messages and contain 1–1,000 characters after trimming.
- Missing or inaccessible messages return HTTP 404. Invalid requests return 400, oversized JSON returns 413, unsupported media types return 415, and unsuitable reply lengths return 422. Unconfigured, busy, failed, or timed-out synthesis returns 503.
- Sora invokes the installed Piper CLI with the explicit local model. The reply travels over stdin and the WAV is read from a private temporary directory that is removed on completion or failure. The backend returns audio for the client to play on request. It opens no playback device and writes no audio to account history.

## Optional setup

1. Run `.venv/bin/python -m pip install -r requirements/voice.txt` in Sora. This installs the optional Linux voice dependencies. Piper runs as a separate CLI and the project does not redistribute the runtime. [Piper CLI documentation](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md)
2. Download `en_US-ljspeech-medium.onnx` and its matching `.onnx.json` into the same directory outside Git. The test used the US-English LJSpeech voice. [Published voice files](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/ljspeech/medium) · [Model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ljspeech/medium/MODEL_CARD)
3. Set `SORA_PIPER_MODEL_PATH` to the absolute path of the `.onnx` file in the backend process environment before launching Sora. The model and runtime are installed once and synthesis uses local files.

## Verified

- `SORA_TEST_VOICE_MODEL_DIR=/tmp/sora-phase-41-model/vosk-model-small-en-us-0.15 SORA_TEST_PIPER_MODEL_PATH=/tmp/sora-phase-42-model/en_US-ljspeech-medium.onnx PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-phase-34-venv/bin/python -B -m pytest -p no:cacheprovider -q -rP tests/test_voice_input.py tests/test_local_single_device_mode.py tests/test_chat_error_copy.py` — exit 0, 50 passed.
- The authenticated endpoint produced 2.84 s of non-silent 16-bit mono WAV in 1.42 s using real Piper 1.8.0. The same run verified real offline Vosk transcription. Tests check unauthenticated requests, cross-user isolation, unsupported inputs, and cleanup after an engine timeout.
- These checks verify the WAV and backend path. Speaker playback, subjective voice quality, and emotional delivery remain unchecked.

## Claude Code handoff

Import the cumulative Phase 4.2 bundle into a clean Sora checkout using `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. It includes the unpublished Phase 3.4, 3.5, and 4.1 commits. Publish through authenticated GitHub access to Emii31/Sora on `origin/main`. The next backend milestone is a complete offline voice-turn smoke test through transcription, the existing chat routes, and speech synthesis.
