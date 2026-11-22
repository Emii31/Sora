# Phase 4.52 — Diagnose sentence endings and voice latency

Used generated English speech and a muted PipeWire sink. The benchmark did not open a physical microphone or store personal audio. Local Qwen, Vosk, and native Sopro ran through the existing terminal prototype with disposable Sora accounts. The approved Liquid reference audio and the Sopro synthesis settings were retained.

## Sentence endings

Five fixtures covered ordinary speech, a second phrase with a different synthetic speaker, a 400 ms pause, a 1,000 ms pause, and a quiet final word. The default 900 ms cutoff captured the final word in four fixtures and omitted it after the 1,000 ms pause. The 1,200 ms cutoff captured that final word in the PCM, but Vosk still mistranscribed the complete phrase. The full-input Vosk control also misheard it. This reproduces independent capture and recognition errors with synthetic speech. The live Phase 4.51 recording was discarded, so its exact failure cannot be attributed to either cause.

Added the opt-in CLI flag `--silence-ms` and kept the 900 ms default. The 1,200 ms setting is a diagnostic option for pausing speakers. Whisper tiny.en preserved “day” in all four complete versions of the “I had a long day” fixture, but transcribed “had” as “have.” It correctly recognized “Please close the window,” which Vosk misheard. Whisper took 1.63–2.36 seconds on the 1,200 ms captures after model load, so this batch decoder was kept out of the live path.

## Reply timing

Two paced runs reused the same one-second-pause fixture. Each setting was measured once. The recognized inputs and replies differed, so the totals cannot establish that either cutoff is faster.

| Stage (seconds) | 900 ms | 1,200 ms |
| --- | ---: | ---: |
| Endpoint silence | 0.90 | 1.20 |
| Vosk finalization | 0.06 | 0.11 |
| Capture teardown | 0.37 | 0.11 |
| Estimated speech end to chat start | 1.34 | 1.44 |
| Chat text generation | 3.25 | 3.31 |
| From chat completion to first Sopro PCM | 4.56 | 2.78 |
| From first PCM to playback submission | <0.01 | <0.01 |
| From estimated speech end to playback submission | 9.16 | 7.53 |

Speech end is inferred from quiet PCM frames. On the prematurely cut turn it refers to the pause measured by the detector. Playback timing measures submission to the playback process. Actual speaker output and mobile latency were outside this test. Both runs saved one exchange in disposable storage and cleaned up. The main measured delays were chat generation and Sopro synthesis startup. Playback diagnostics estimated two and three gaps respectively.

## Verification

- `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_liquid_live.py tests/test_voice_input.py tests/test_voice_sopro_live.py tests/test_voice_context.py tests/test_voice_continuous.py tests/test_voice_sentences.py tests/test_voice_brain.py tests/test_voice_playback_diagnostics.py` exited 0 with 160 passed, 6 skipped.
- `PYTHONPATH=. .venv/bin/python scripts/live_liquid_voice.py --help` listed the option. A 2,001 ms value returned exit 2 before initializing the voice pipeline.
- Scratch scripts and generated fixtures are in `/mnt/data/Companion/recovery/phase_04_52`. `probe-endings.py` generated the fixtures and ran the Vosk comparison. `verify-stages.py one_second_pause 900` and `verify-stages.py one_second_pause 1200` ran the paced comparisons. `compare-whisper.py` used the existing local Whisper runtime. All successful benchmark commands exited 0.
- JSON evidence is in `docs/verification/phase_04_52`. The temporary sink and CLI test processes were confirmed removed.

Next, benchmark beginning speech on the first complete reply sentence while chat generates the rest. Match the response text and measure continuity, then decide whether a further live phone trial is useful.
