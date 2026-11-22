# Phase 4.56 — Motorola voice acceleration

The owner asked to make the approved Motorola voice suitable for live chat. The fastest successfully measured path synthesized on the Motorola and started near two seconds from ready text. The complete reply test still missed the existing two-second conversation target. The Phase 4.55 voice remains the approved baseline.

## Matched phone synthesis

All successful profiles received the same three lines, the same 10-second Liquid-derived voice reference, and the same seeds. The first LiteRT request was cold for the voice; the next two used a prepared voice cache. Native measured requests were all warmed by a separate request.

| Backend | First PCM for the three lines | Result |
| --- | --- | --- |
| Approved LiteRT CPU | 15.76 / 13.16 / 12.11 s | Owner-approved baseline |
| LiteRT acoustic GPU | 11.39 / 8.28 / 8.57 s | All words preserved, 98–100% high-confidence waveform anchor matches |
| LiteRT acoustics GPU with speech token generation GPU FP32 | 15.00 / 11.92 / 12.64 s | All words preserved, substantially different waveform, slower than acoustic-only |
| LiteRT acoustics GPU with default-precision GPU speech token generation | No PCM | Sampler precondition failure |
| Native ARM, two unpinned threads | 1.89 / 1.89 / 2.48 s | Estimated continuous speech start 1.95–2.52 s |
| Native ARM, three unpinned threads | 1.81 / 1.84 / 2.47 s | Estimated continuous speech start 1.91–2.51 s |

The two successful native settings produced identical PCM to each other and retained every word according to local Whisper. The native streaming waveform differs from LiteRT because the two implementations decode speech differently. The owner has approved LiteRT's delivery. Listening acceptance of the native candidate remains pending. Two four-thread pinned runs timed out during warmup, including one with the screen held awake. The successful native tests kept the phone awake temporarily. Screen-off reliability is open. Two-thread first PCM for the cold warmup sentence was 6.05 s after its request, with process loading excluded.

## Actual local chat integration test

Used real local Qwen 2.5 1.5B and the existing Sora turn flow with native phone TTS over temporary USB forwarding. Submitted two synthetic recognized-text inputs. Playback went to a muted laptop sink. Both completed and persisted exactly one exchange each in disposable history. Start from recognized text was 3.47 and 3.59 s. Offline waveform alignment measured zero added delay in both virtual playback captures. The test excludes speech recognition, endpointing and physical phone speaker playback. Voice latency from the end of live speech is still open.

## Reproduction and cleanup

- Ran `python3 -B -u run-profile.py acoustic-gpu`, `ar-gpu32`, and `ar-gpu` from `/mnt/data/Companion/recovery/phase_04_56`. The first two commands exited 0. The default-precision GPU run exited 1 with the recorded sampler failure. The 112,061,680-byte optional graph was checked against its pinned Hugging Face checksum before transfer and on Android.
- Cross-built audio.cpp v0.9.6 with Android NDK r27d, arm64-v8a, API 28, and `armv8.2-a+dotprod+fp16`, supported by the phone. The stock cross-link lacked Android logging. The scratch build links `log` for its server target, and the relink exited 0. The checkpoint and reference checksums were verified across USB.
- Ran `python3 -B -u native-phone.py native-awake-2 2 unpinned` and `native-awake-3 3 unpinned`, exit 0. The initial pinned diagnostic exposed an audio event without rate metadata. Verified 24 kHz mono in the pinned model and server contract and used that value when the server omits the field. Later pinned trials hit the bounded stream timeout.
- Ran `PYTHONPATH=/mnt/data/Companion/Miru:/mnt/data/Companion/Miru/scripts /mnt/data/Companion/Miru/.venv/bin/python -B -u integrated-voice-turn.py 2 unpinned`, exit 0. Local Whisper checks and waveform alignment saved in the phase evidence. The approved APK and original reference audio are preserved.
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_sopro_live.py tests/test_voice_brain.py tests/test_voice_context.py tests/test_voice_playback_diagnostics.py`, exit 0 with 46 passed. Phone cleanup verified all three restored WAVs byte-for-byte and zero remaining ADB forwards.
- The phase changes only project records. The scratch build, scripts, saved timings, and audition WAVs remain in recovery. Phone cleanup removes owned native files and forwards and restores the original sleep setting and approved audition outputs.

Next measure how much of the remaining delay comes from waiting for the complete chat response, and compare any candidate using final-word accuracy, prompt response time, continuity, and the owner's on-phone listening check.

[audio.cpp Sopro streaming and prepared voice cache](https://github.com/0xShug0/audio.cpp/blob/v0.9.6/docs/models/sopro_tts.md)
