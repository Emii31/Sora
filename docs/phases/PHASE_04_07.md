# Phase 4.7 — Real Local Vision Smoke Test

## Setup

The smoke test requires a running loopback Ollama instance and an installed image-capable model. The test configures the vision tier in a disposable data directory, generates two synthetic frames, and submits each through the authenticated Flask route. It checks the result for the expected color, verifies that the descriptions differ, and checks that the route leaves the files and chat history alone.

On this laptop, the test uses Ollama 0.40.16 and `moondream:1.8b`, which requires about 1.7 GB of download space. The model is fetched once and inference uses Ollama's local runtime. The test uses a separate model cache and keeps the default Ollama instance and the production Sora data out of the test. [Moondream model card](https://ollama.com/library/moondream:1.8b) [Ollama local-only mode](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)

## Reproduce

Run the temporary server in one terminal. Choose an existing writable cache location for `OLLAMA_MODELS`.

```bash
OLLAMA_HOST=127.0.0.1:11436 OLLAMA_MODELS=/path/to/vision-models \
  OLLAMA_NO_CLOUD=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
  CUDA_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 ollama serve
```

In a second terminal, download the model once. From the Sora checkout, then run the smoke test with the project's Python environment.

```bash
OLLAMA_HOST=127.0.0.1:11436 ollama pull moondream:1.8b
SORA_TEST_VISION_URL=http://127.0.0.1:11436/v1 \
  SORA_TEST_VISION_MODEL=moondream:1.8b \
  PYTHONPATH=. .venv/bin/python -m pytest -q -s tests/test_camera_input.py
```

Stop the temporary server with Ctrl+C when done. The test uses a generated image, without using a physical camera.

## Results

- Ollama reported cloud features disabled and started its CPU runner with `--offline`. Both requests reached its loopback `/v1/chat/completions` endpoint and returned HTTP 200. The temporary server was stopped after the test.
- On the Intel i5-7300U with 8 GB RAM, the first frame took 61.69 s including cold model loading. The second frame took 50.44 s with the model loaded. The model described a “red square with white borders” and a “blue circle with a white border,” respectively. These two samples verify integration and color and shape recognition on simple images. They provide no latency or accuracy estimate for general camera scenes.
- Live command: `SORA_TEST_VISION_URL=http://127.0.0.1:11436/v1 SORA_TEST_VISION_MODEL=moondream:1.8b PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q -s --tb=short tests/test_camera_input.py`. Exit 0, 17 passed.
- Regression command: `SORA_TEST_VOICE_MODEL_DIR=/tmp/sora-45-model/vosk-model-small-en-us-0.15 SORA_TEST_PIPER_MODEL_PATH=/tmp/sora-44-model/en_US-ljspeech-medium.onnx PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q -rs --tb=short tests/test_camera_input.py tests/test_chat_image_history.py tests/test_chat_image_upload_disabled.py tests/test_local_single_device_mode.py tests/test_voice_input.py tests/test_ai_config.py tests/test_shared_provider.py`. Exit 0, 135 passed with the live vision and combined voice-turn tests skipped in that run.
- Application code was unchanged. The reusable integration test is in `tests/test_camera_input.py`. Model weights are in a separate local Ollama cache and are excluded from Git.

## Claude Code handoff

Review this record and `docs/STATUS.md` before continuing. The cumulative Phase 4.7 Git bundle can be imported with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. The bundle requires Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`) and includes the backend work through this phase. Continue with the shared-memory backend audit while app and device integration remain deferred.
