# Phase 4.17 — Faster Playback for the Approved Voice

The owner asked to keep the selected Qwen voice and improve its latency. This phase uses the same 0.6B Base talker, codec, speaker embedding, acoustic reference, reference transcript, and seed as Phase 4.16. The approved reference WAV still has SHA-256 `5ad5d7d8073ad5fb19c0abbf33373203600612f95d30e8432a53de0cb062946c`.

## Enable the tested setup

The local voice kit includes the Intel Vulkan runtime under `sora-approved-voice/vulkan`. Before starting Sora, set:

```bash
export SORA_QWEN_VOICE_DIR=/absolute/path/to/sora-approved-voice
export SORA_QWEN_RESIDENT_DEVICE=Vulkan0
```

The serving process primes Qwen with a short discarded utterance at startup, or when its local-only mode starts. Synthesis may report busy during this one-time warm-up. The process and decoded reference remain in memory between replies. The normal authenticated endpoint returns a complete WAV. Reply text and PCM travel over private subprocess pipes. No listening service or persistent audio file is needed. When the resident setting is absent, the Phase 4.16 Qwen CLI or Piper configuration continues to apply. A failed resident process is discarded and the next request can start a new one.

## Rebuild the binary

Start with qwentts.cpp at `f1a6924789883bd92eeb59176793a94af55730b3` and GGML at `0d403add5cb6329935290f02462e1072045aacd2`. Apply Sora's `scripts/qwen-sora-frames.patch` with `git apply --unidiff-zero <path-to-patch>` to the pinned runtime source. Build the `qwen-tts` target in Release mode with `GGML_VULKAN=ON`, `GGML_NATIVE=ON` and `CMAKE_BUILD_RPATH_USE_ORIGIN=ON`. This run used Vulkan-Headers `6802bb4733b63ed5efd3adb308a6c885ef180ea1` and SPIRV-Headers `ad9184e76a66b1001c29db9b0a3e87f646c64de0` in a temporary build prefix. Place the executable as `vulkan/qwen-tts-framed` with its `libggml*.so*` libraries in the kit.

The patch adds a little-endian size before each PCM chunk and a zero-length marker at a successful end of reply. Other CLI modes are unchanged. The Python process verifies boundaries, enforces the existing frame limit and timeout, and closes the worker if the pipe breaks or yields an invalid chunk.

## Verification

- The real Flask endpoint synthesized two saved assistant replies for a disposable account using Vulkan0 (Intel HD Graphics 620). It returned HTTP 200 and 24 kHz mono PCM16 both times. Both used the same worker process. The warm-up workload took 27.33 seconds.
- The same text as Phase 4.16 rendered a 3.68-second clip in 24.97 seconds, compared with 62.85 seconds for the earlier CPU route measurement. A second 4.48-second clip took 28.53 seconds. These timings measure saved reply to completed WAV, excluding chat. Vosk recovered the full words in both samples and the PCM peaks were 12,006 and 18,541 with no clipping. The samples are `sora-same-voice-fast-reply1.wav` and `sora-same-voice-fast-reply2.wav` in the audition directory.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -B -m pytest -p no:cacheprovider tests/test_voice_input.py tests/test_local_single_device_mode.py -q` exited 0. 64 passed and six optional live tests skipped. Reuse, malformed-frame cleanup, WAV format, and configuration were checked. The live Flask harness was run separately as `SORA_AUDITION_ROOT=<artifact-parent> GGML_VK_VISIBLE_DEVICES=0 PYTHONPATH=. python -Bu <kit>/verify-resident-replies.py`, exit 0.
- Realtime playback and device UI deployment remain pending. The normal project drive is unavailable. The recovery checkout checkpoint is packaged as `Sora-through-phase-4.17.bundle` for a fast-forward import. Runtime and model files are stored outside Git.
