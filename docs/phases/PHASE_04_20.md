# Phase 4.20 — Same-Line Chatterbox Nano Audition

The owner approved a standalone listening test for Chatterbox Nano. The audition conditions on the approved 7.12-second Sora reference WAV, SHA-256 `5ad5d7d8073ad5fb19c0abbf33373203600612f95d30e8432a53de0cb062946c`. All four takes use identical words, punctuation and random seed. The plain take uses no delivery tag. The next three request warmth using `[happy]`, playfulness using `[chuckle]`, and concern using `[fear]`. Those labels describe the requested delivery. Review the clip by ear to judge the voice likeness and expression.

## CPU measurements

| Take | WAV duration | Generation time |
| --- | ---: | ---: |
| Plain | 3.08 s | 14.45 s |
| Warm | 3.64 s | 16.68 s |
| Playful | 3.48 s | 16.73 s |
| Concerned | 3.76 s | 17.18 s |

The i5-7300U run used two CPU threads, PyTorch 2.6.0 CPU, and the official model revision `71ccd1d0081b430592cea481f4307e764e07bc64`. Source revision `ab55923c27757c90cfcc407baa57dc25a7d25217`. The CPU runtime used the published Perth 1.0.1 wheel after the upstream Git dependency download stalled. `pip check` exited 0. Loading the model took 22.28 seconds, the reference setup took 29.09 seconds, and a warm-up utterance took 6.78 seconds. The table excludes those startup steps. Peak process RSS was 4,045.7 MiB. The tested API returned a completed waveform per request. Live conversation latency and concurrent chat inference were outside this audition. [Chatterbox Nano model card](https://huggingface.co/ResembleAI/chatterbox-nano)

## Audio verification

The benchmark ran with Hugging Face offline settings and a socket-denying Python audit hook. It used the original model assets, with SHA-256 verification of the downloaded weights. All four source WAVs were distinct, non-silent, and free from sample clipping. Vosk recognized the same sentence in each take apart from collapsing “want to” to “wanna” in the playful take. The comparison reel combines the 24 kHz mono PCM16 files in order, with one second of silence between them. The reel is 16.96 seconds and has SHA-256 `76725f8a582ea216cd024603a81afc0e98d455d1a6a350df489630c576658747`.

The listening files, harness and render logs are stored outside Git under `sora-nano-audition/` in the conversation artifacts. The isolated runtime and verified weights are under `/mnt/data/Companion/sora-nano-audition/`. The owner can assess whether the voice and delivery justify any further optimization or integration.
