# Phase 4.47 — Find a faster match for the approved Liquid voice

The approved Liquid reel remains the listening baseline. Tested two local reference-conditioned models on the i5-7300U. No replacement meets the speed and clarity checks in this batch. The speech target is 1.2 s to estimated continuous audible playback after the reply text is available, excluding speech recognition, chat generation and the physical speaker. Subjective similarity remains owner-reviewed.

| Candidate | Test | Outcome |
| --- | --- | --- |
| Sopro V2 Turbo 2.2.0, INT8 | Four CPU threads, two published solver steps, cached references drawn from the approved celebration, cookie and reassurance takes. Five distinct turns. | First PCM 1.09–3.31 s. Continuous audible start estimated at 2.61–7.76 s. Whisper tiny.en recovered all 81 words. |
| Sopro V2 Turbo 2.2.0, INT8 | Two CPU threads, same cases | Continuous audible start 3.82–6.23 s. |
| LuxTTS INT8 | Four CPU threads, four sampling steps, 2.54-second excerpt from the approved celebration take | Estimated audible start 2.16–4.97 s. Whisper recorded 6 edits in 52 words. The shortest reply was truncated to “Oh.” |

Sopro is the cleaner local result. The Android LiteRT port is a separate deployment whose publisher reports a 2.066 s median first-audio time on a Galaxy S26 with its hybrid GPU/CPU build. That deployment was reviewed but not run on the Motorola. The published configuration completes autoregressive generation before acoustic decoding. Its results do not establish Motorola performance.

The Sopro snapshot is `c12d0dc7c4a33b3cb6ea3d11ceb70bc60c7c6312`. The LuxTTS graph snapshot is `527f245a276a0eb42ea103a7a512bcfd771eb9b6`, with CPU-only runner revision `d29f673417d3bd8f82b8a2dda0131eb3eb6078e2` and Vocos snapshot `454a62c256d65e2afeb644d95e9fde16b09f590c`. Weight hashes were checked before inference. Test audio, full PCM-arrival timing reports, transcripts, logs and scripts are under `/mnt/data/Companion/recovery/phase_04_47`. The approved WAV passed its checksum check.

- [Sopro V2 Turbo](https://huggingface.co/samuel-vitorino/sopro-v2-turbo)
- [Sopro Android deployment and timings](https://huggingface.co/litert-community/sopro-v2-turbo#android)
- [LuxTTS](https://huggingface.co/YatharthS/LuxTTS)
