# Phase 4.16 — Approved Sora Voice in the Backend

Use the exact owner-approved Phase 4.15 WAV as the reference for new replies. The reference SHA-256 is `5ad5d7d8073ad5fb19c0abbf33373203600612f95d30e8432a53de0cb062946c`. Its transcript is in the runtime directory alongside its speaker embedding and frame codes.

## Local setup

Set `SORA_QWEN_VOICE_DIR` to the supplied `sora-approved-voice` directory before starting Sora. The directory contains the CPU-native Linux executable and libraries, two model symlinks, and the encoded reference. Keep its sibling `sora-qwen-voice-assets` directory in place. The backend uses Qwen for default playback when configured. A missing file or render failure returns an unavailable response. The existing Piper configuration applies when the Qwen setting is absent.

The authenticated `POST /api/voice/synthesize` route accepts the saved assistant reply ID with its default style. Qwen Base renders the reference delivery, with a 240-character reply limit and a 180-second process timeout. Synthesis runs in a private temporary directory and passes reply text on stdin. Model downloads are a setup step. Generation uses local files.

The kit uses qwentts.cpp at `f1a6924789883bd92eeb59176793a94af55730b3` and its GGML submodule at `0d403add5cb6329935290f02462e1072045aacd2`. The build used `GGML_NATIVE=ON` and `CMAKE_BUILD_RPATH_USE_ORIGIN=ON`. Both Q4_K_M models are pinned to the published [GGUF revision](https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/tree/b7ee2e8c7459c3bea99da23e3d178125a7d1713c) and verified against its SHA-256 digests.

- Talker, 628,905,056 bytes, `4b468ec7b1f62b90ef4ca316c0aa57deadfd54b2cf9651703ea753cedaf04226`
- Codec, 254,974,752 bytes, `cf3788b4d50aaa665fb6e57c170396aae03a3555fea52d2b5d0cda902d658039`

Run this command inside the kit to rebuild the reference files from the saved copy:

```bash
./qwen-codec --device CPU --model sora-codec.gguf --talker sora-base.gguf -i reference.wav
```

## Verification

- On the i5-7300U laptop, an authenticated disposable account sent a new prompt through `POST /api/chat` with local Ollama `qwen2.5:1.5b-instruct`. The worker selected `reactive_fast` and saved the exact assistant reply “Great job, you've earned a well-deserved break!” in 23.71 seconds.
- `POST /api/voice/synthesize` read that reply from real history and returned HTTP 200 with 3.60 seconds of 24 kHz mono PCM16 audio. Synthesis took 62.85 seconds wall time. The child process peaked at 2,688 MiB RSS. The file is saved as `sora-qwen-audition/sora-approved-voice-new-reply.wav`. Local Vosk recovered the entire sentence. The PCM peak was 16,132 with no clipping, and the output SHA-256 is `6348a43ceda57ebeeb40fa3ac8b490efc1a753ad2a6e673d4c2d7244e56a1f71`. The disposable live-check script is `sora-approved-voice/verify-live-reply.py` beside the model assets. It requires local Ollama and `SORA_416_ARTIFACT` set to their common parent directory.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -B -m pytest -p no:cacheprovider tests/test_voice_input.py tests/test_benchmark_chat.py tests/test_chat_preflight_routing.py tests/test_user_settings.py tests/test_shared_provider.py -q` exited 0 in the isolated Python 3.11 environment. 83 passed, six optional live tests skipped, and two existing Pillow warnings were reported. `python -m pip check` exited 0.
- The normal project drive was unavailable. This phase was implemented in the recovery checkout and packaged in `Sora-through-phase-4.16.bundle`. Import it from a clean checkout by running `git fetch <bundle-path> main` followed by `git merge --ff-only FETCH_HEAD`. The model files, reference, and generated example are stored alongside the bundle.
- Interactive playback deployment remains pending. This single render establishes a working backend path. Broad emotional range and perceived speaker consistency require listening across more replies. The measured CPU latency is too high for conversational playback.
