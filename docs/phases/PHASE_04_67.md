# Phase 4.67 — Direct speech-to-speech latency screen

Selected Liquid LFM3-Audio 2B for one bounded offline test. It is a new architecture relative to both Sopro and the earlier LFM2.5 trial. Its realtime interface consumes audio as it arrives and streams output audio from the same model. The publisher's desktop codec throughput describes a component on different hardware. Qualification requires timing on the Motorola. [Liquid model card](https://huggingface.co/LiquidAI/LFM3-Audio-2B-GGUF), [realtime API](https://github.com/ggml-org/llama.cpp/blob/b11960/tools/server/README.md#realtime-conversation)

Kept the approved Sopro voice available. Screened the published Q4_0 model and matching Q4_0 projector against the official Android ARM64 CPU release of llama.cpp b11960. This is an audition, with no default voice or production code changes.

## Method

Used the same synthetic favorite-color, tea, recall, long-day and cookie inputs as recent Motorola tests. The Android server processed PCM while the host supplied it in 80 ms chunks at recording speed over a temporary USB forward. The fixture's known final speech frame triggered a 320 ms tail before requesting the answer. This is a favorable prerecorded endpoint. It does not establish that a live endpoint can preserve a user's hesitations at this delay. The host measured the first 20 ms of response PCM above the speech energy threshold. The measurement excludes speaker buffering and contains USB transport. All candidate inference ran on the phone. The microphone remained closed.

The qualification gate was two seconds to speech-level PCM even before the speaker test. A candidate that passes this screen still needs measured speaker onset, continuous delivery, and the owner's listening approval. PCM arrival records also estimate how much startup reserve would be needed to keep audio supplied at playback speed. That estimate is not an Android underrun measurement.

## Result

| Measured turn | First PCM | First speech-level PCM | Additional reserve estimate |
| --- | ---: | ---: | ---: |
| State favorite color | 1.09 s | 7.71 s | 15.70 s |
| Tea | 0.99 s | 4.91 s | 10.92 s |
| Recall favorite color | 0.95 s | 7.44 s | 15.63 s |
| Long day | — | No speech-level output | — |
| Cookie | — | Unreached | — |

The table uses the second run, which set a limit of 96 output steps per request. The initial run also missed the target at 7.33 s on the favorite-color turn and stopped during the tea turn when a delta failed the audio guard. The capped run's reassurance turn ended with a completion event and no audio deltas. This stopped the run before cookie. All three timed outputs missed the two-second gate. The first PCM packets had low energy. Offline Whisper recovered fragments or sighs, and it did not recover blue from the recall output. This was an automated signal and intelligibility check. No audio was played through the speaker and voice acceptance was not assessed.

Reject this tested build and model pairing for live Motorola use. The approved Sopro setup remains the known working voice. Future candidates should qualify by on-device speech onset and continuous output before a listening audition. No candidate has qualified in this phase.

## Verification

- Fetched the publisher's `39670cb5c42e9c4bfe046519ba7ffbe47f9552ad` LFM3 GGUF manifest and the official [llama.cpp b11960 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11960). Resumed interrupted byte ranges and verified both GGUF hashes and the Android archive against publisher metadata.
- From `/mnt/data/Companion/recovery/phase_04_67`, staged the runtime and models with `stage-device.py`, verifying their hashes on the Motorola. The first device reconnect was sufficient for the projector transfer. A second reconnect was required before the main model transfer. The binary ran with four CPU threads and no accelerator.
- Ran `bash with-awake-phone.sh /mnt/data/Companion/Miru/.venv/bin/python -B -u latency.py primary` with the initial harness, then repeated with the capped harness and `capped` label. Both exits were 1 for the causes above. All measured outcomes remained available. Ran `source ../phase_04_59/env.sh && /mnt/data/Companion/Miru/.venv/bin/python -B inspect_result.py capped` and the matching `primary` command. Both audio inspections exited 0. See [initial screen](../verification/phase_04_67/initial-screen.json) and [capped screen](../verification/phase_04_67/capped-screen.json).
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_brain.py tests/test_voice_context.py tests/test_voice_sopro_live.py tests/test_voice_playback_diagnostics.py` in the repo. 51 passed, exit 0.
- Removed the owned Android test folder, verified no forwarded ports remained and confirmed the restored stay-awake setting was 0.
