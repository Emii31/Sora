# Phase 4.6 — On-request Camera Input Backend

## API contract

An authenticated client can send one still frame to `POST /api/camera/describe` after the user requests camera input. Send raw bytes with `Content-Type: image/jpeg` or `image/png`. The endpoint accepts up to 4 MiB and 4,096 pixels per side. It applies orientation, reduces the longest side to 768 pixels when needed, and re-encodes to JPEG without source metadata. On success it returns `{"description":"..."}` with caching disabled. Invalid images, unsupported content types, oversized bodies, and unavailable vision return 400, 415, 413, and 503 respectively.

The caller controls capture and decides what to do with the description. The backend processes one frame at a time in memory and does not append it or the description to uploads, chat, or memory. This phase adds no camera capture, streaming, or permission prompts. Client integration will need to tie the capture to an explicit user action.

The existing vision-tier model, base URL, and API key are used. The endpoint sends one OpenAI-compatible request to a loopback IP and disables proxy inheritance and HTTP redirects. Configure a vision-capable model on the same host as the Sora backend. For Ollama, set `OLLAMA_NO_CLOUD=1` on the server and select a locally installed vision model. Sora cannot verify how a separate loopback service handles data internally. [Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx) [HTTPX environment variables](https://www.python-httpx.org/environment_variables/)

## Verification and handoff

The Flask route exchanged a generated blue frame with a disposable HTTP test server bound to `127.0.0.1`, with a nonfunctional environment proxy set. The test server decoded the JPEG and received the expected vision model ID and path. A real vision-model run is pending. This machine had only the text model `qwen2.5:1.5b-instruct` cached, and no camera was used.

Files changed include `app.py`, `camera_input.py`, `tests/test_camera_input.py`, and phase and project records. Import the cumulative Phase 4.6 bundle into the clean Sora checkout with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. The bundle begins at Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). Publish to Emii31/Sora on `origin/main` with authenticated access. Verify an installed local vision model before connecting real camera capture, and keep web, desktop, and Android app work deferred.

- Focused command: `SORA_TEST_VOICE_MODEL_DIR=/tmp/sora-45-model/vosk-model-small-en-us-0.15 SORA_TEST_PIPER_MODEL_PATH=/tmp/sora-44-model/en_US-ljspeech-medium.onnx PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q -rs --tb=short tests/test_camera_input.py tests/test_chat_image_history.py tests/test_chat_image_upload_disabled.py tests/test_local_single_device_mode.py tests/test_voice_input.py tests/test_ai_config.py tests/test_shared_provider.py`. Exit 0, 135 passed and one optional Ollama voice-turn test skipped.
- Loopback smoke command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B /tmp/sora-46-loopback.py`. Exit 0. The disposable smoke script used a generated image and a temporary application data directory.
