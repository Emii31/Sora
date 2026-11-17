# Phase 4.23 — Stream Recognition into Liquid's Chat Voice

The owner chose the default Liquid chat voice from the 45-second tone comparison. This standalone prototype keeps the interleaved text-and-audio prompt from Phase 4.22 and feeds it text from the existing local Vosk model. This is distinct from Liquid's dedicated UK female TTS mode.

The benchmark replays the same three prerecorded WAV fixtures at capture speed, delivering 80 ms blocks to Vosk and finalizing at the end. It sends the transcript to Liquid's default chat mode over loopback. The direct baseline sends the same WAV after the input would have ended. The runner stays loaded on four CPU threads, resets chat context each turn, and alternates path order across fixtures. The loopback-only namespace has no internet route.

## Measured after input ends

| Fixture | Vosk finalization | First voiced chunk via Vosk / direct | Smooth audible start via Vosk / direct |
| --- | ---: | ---: | ---: |
| Check-in | 0.046 s | 4.09 / 4.19 s | 7.64 / 9.06 s |
| Good news | 0.157 s | 2.88 / 3.79 s | 8.88 / 7.17 s |
| Comfort | 0.047 s | 3.36 / 4.96 s | 16.15 / 8.64 s |

The smooth start is estimated from audio-chunk arrivals and an audible onset threshold. Liquid returned different replies for the two paths. In the comfort case, it produced 16.94 seconds of speech from the transcript and 4.38 seconds from the direct audio. The first voiced chunk improved in each pair, while sustained playback became slower in two cases. The two-second target for smooth playback remains unmet. The prototype uses prerecorded fixtures and does not measure live endpoint detection, speaker latency or interruption.

## Reproduction and evidence

Run `PYTHONPATH=. python scripts/benchmark_liquid_text_bridge.py --kit <local-liquid-kit> --vosk-model <local-vosk-model> --output <result-dir> <16-kHz-mono-PCM16-WAVs>`. The test ran this inside a fresh user/network namespace, enabled only loopback, and pointed `LD_LIBRARY_PATH` to the supplied Linux runner directory. The real run exited 0. All six responses received stop events and yielded non-silent 24 kHz mono PCM16 WAVs. Timing output and sample audio are under `sora-liquid-audition/voice-bridge/` in the conversation artifacts.
