# Phase 4.66 — Phone-only conversation feasibility test

Ran recognition, generation, synthesis and speaker output on the Motorola. Separate resident Android workers used Whisper tiny.en and the exact Qwen2.5 1.5B Instruct model from the existing Ollama manifest. The phone used a disposable copy of Sora's system prompt and carried the last five messages across turns. Sopro received one request per complete reply with the approved reference, two threads, original synthesis settings, seed 9000 and a 0.75-second playback buffer. Sopro, Whisper and Qwen warmed up before the measured turns.

The Android harness replayed the prerecorded files at 20 ms intervals, used the existing 1.2-second endpoint and timed playback with Android's monotonic clock. Estimated speech onset uses the AAudio frame presentation timestamp and the first speech-level window in the reply PCM. USB staged files, started the benchmark and collected logs. No inference requests, input audio or playback PCM went through the laptop during the run. ADB forward and reverse lists were empty. The microphone stayed closed.

| Fixture | End of input speech to reply audio | Android underruns |
| --- | ---: | ---: |
| State favorite color | 5.32 s | 0 |
| Tea | 5.77 s | 0 |
| Recall favorite color | 5.14 s | 0 |
| Long day | 7.38 s | 0 |
| Cookie | 8.00 s | 0 |
| Median | 5.77 s | 0 |

All five replies drained to the built-in speaker and the phone saved exactly ten matching synthetic history messages. Sora recalled blue after the intervening tea turn. Whisper heard “I have a long day” for the long-day fixture. This verified the phone-only path with recordings. Live microphone behavior, Android background execution and cross-device sync were outside this test.

The median endpoint wait was 1.20 s, recognition took 0.35 s, Qwen took 1.33 s and Sopro took 1.97 s to first PCM from ready text. Those stage medians may come from different turns. Phase 4.65's laptop-assisted median was 6.78 s. Different run lengths, session history, generated text and Qwen runtimes make that a reference point. It is not a matched estimate of offloading speed.

## Decision

The measured phone-only pipeline misses the two-second target by a wide margin. Keep the approved Sopro setup available and stop repeating incremental tuning of this pipeline for that target. A separate offline voice architecture would have to demonstrate both the desired delivery and near-two-second onset on this phone before app integration. Voice replacement remains a separate decision.

## Verification

- Built the ARM64 Whisper worker from upstream [Whisper.cpp v1.8.5](https://github.com/ggml-org/whisper.cpp/tree/v1.8.5) using the existing NDK. The downloaded archive hash was `cd702189cb5e608c8bc487f4b151db593c4455925b37cc06ef76b44861911db1`. The tiny.en weights were the same local artifact used in Phase 4.65.
- Built the chat worker against the existing Android llama.cpp libraries at revision `ec9d1fdd9cc18643c5e161b65b8053f6f6f34a4b`. Staging verified the Qwen GGUF hash against its Ollama manifest and verified transferred files on the phone.
- From `/mnt/data/Companion/recovery/phase_04_66`, ran `bash build-chat.sh`, `bash build-asr.sh` and `bash build-driver.sh`, then `bash with-awake-phone.sh python3 -B stage.py` and `bash with-awake-phone.sh python3 -B run_device.py`. Final builds and the benchmark exited 0. Scratch harness sources and logs remain in that directory. Structured results contain only [synthetic inputs, replies and timings](../verification/phase_04_66/motorola-phone-only.json).
- From the Sora repository, ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_brain.py tests/test_voice_context.py tests/test_voice_input.py tests/test_voice_sopro_live.py tests/test_voice_playback_diagnostics.py`. 91 passed and six skipped, exit 0.
- Removed the owned Android test directory after checking the history file. Verified empty forwarding lists and restored stay-awake value 0.
