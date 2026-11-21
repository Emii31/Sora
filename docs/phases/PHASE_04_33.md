# Phase 4.33 — Liquid stage timing and stock offline voice audition

On 2026-11-21, profiled the selected Liquid voice on the Motorola and compared released CPU voices on the Core i5-7300U laptop. Starting checkpoint was `804e020`. The benchmark used synthetic lines and separate virtual environments for third-party audition packages.

## Liquid on the Motorola

Temporary native counters measured the audio token sampler and detokenization path. The runner also reported its existing backbone prefill and decode counters. The short and long PCM hashes exactly matched Phase 4.32.

| Fixture | Speech duration | Generation wall time | Backbone prefill | Backbone decode | Token sampling | Detokenization |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Short | 3.74 s | 14.61 s | 1.56 s | 7.22 s | 4.91 s | 0.65 s |
| Long | 10.86 s | 22.50 s | 5.55 s | 10.78 s | 6.82 s | 1.76 s |

The native counters have different accounting boundaries and do not sum to host-observed wall time. The main measured costs were the backbone and audio token sampler. The short virtual monitor recorded 8.63 seconds of added time between matched anchors. The long monitor alignment was inconclusive. Generation took 3.91 and 2.07 wall seconds per second of audio. This configuration remains slower than playback.

The diagnostic-only `patches/liquid-stage-profile.patch` applies to the pinned private native checkout after the existing forced-speech patch. The test rebuilt `llama-liquid-audio-server` and called the existing `profile_voice_playback.measure` helper on the Phase 4.32 fixtures with a 0.5-second reserve. The original source and runner binary were restored and the original phone cache was hash-verified through the normal launcher. The temporary phone runner, its lock, and its USB forward were removed after the checks.

## Stock CPU auditions

| Engine and released build | First available PCM | Outcome |
| --- | ---: | --- |
| Kokoro ONNX 0.6.0, Kokoro v1.0 int8, Heart | 12.76–23.50 s over five measured lines | Too slow. The bounded audition ended before all planned lines. |
| Sherpa ONNX 1.13.8, Kitten Nano v0.8 int8, Bella/Luna | 1.57–6.67 s over completed trials | Faster than Kokoro. Start delay varied and several clips took longer to generate than to play. |
| Piper 1.8.0, Amy Low, CPU | 0.08–0.48 s across eight stock trials | Speech engine suitable for interactive output. Two long passes generated 15.17–15.49 seconds of speech in 1.61–1.68 seconds. |

Two additional Piper passes in the network-restricted sandbox generated first PCM in 0.07–0.67 seconds and 15-second clips in 1.54–1.59 seconds. It read cached model files. Amy uses its released default speed and settings. No model changes, training, artificial pacing adjustments or GPU configuration were used. The sandbox retry used the same Piper and ONNX Runtime versions.

Sherpa 2.0.2 no longer loaded the model archive's bundled phonemizer through the documented example. The audition used unmodified Sherpa 1.13.8 with the stock archive. The direct Kitten SDK dependency attempt was stopped after it began pulling large dependencies. Kokoro and Kitten were auditioned as timing candidates and were not installed into Sora. Source and model references are below.

## Local chat playback

With the local Qwen 1.5B chat model warm and synthetic recognized text as input, Piper Amy's three responses started entering PipeWire at **3.08, 3.53 and 5.04 seconds**. Chat generation itself took **2.27–3.79 seconds** and subsequent synthesis took **0.44–0.57 seconds**. The monitor matched all three replies with zero measured added time between anchors. The harness sends a complete generated text reply to stock Piper, and resamples only for the existing diagnostic monitor. These timings exclude the microphone, speech recognition and endpoint detection. The in-app route and natural delivery were outside this check.

Amy is the speed candidate. The owner's evaluation of her female voice and emotional delivery is pending. The 33-second audition contains six new lines across delight, teasing, comfort, firmness, relief and reflection. These are differences in text and context. They are not independent emotion controls. The native-speed audition WAV is at `/mnt/data/Companion/recovery/phase_04_33/piper/stock/amy-audition.wav`. Liquid and the existing application defaults remain in place while the owner evaluates Amy.

## Reproduce and handoff

The following command uses the existing isolated audition environment and cached released Amy files. Use a fresh report directory. Add `--chat` to repeat the loopback playback check when the local Ollama service is running with Qwen installed. Only the test prompt and candidate speech use this harness. It never reads real Sora account data.

```bash
cd /mnt/data/Companion/Miru
root=/mnt/data/Companion/recovery/phase_04_33/piper
PYTHONPATH=. "$root/venv/bin/python" -B scripts/benchmark_stock_voice.py \
  --engine piper --assets "$root" --report /tmp/sora-amy-stock
```

Evidence is under `docs/verification/phase_04_33/`. It records the native counters, short/long PCM hashes, stock comparisons, chat playback checks and existing regression result. All 104 targeted tests passed. Python compilation and source patch applicability passed. WAVs, source backups, models and environments are outside Git. The next work depends on the audition result. If the owner chooses Amy, integrate the proven voice as an option and address the measured chat-model delay separately.

- [Kokoro runtime and official export releases](https://github.com/thewh1teagle/kokoro-onnx/releases)
- [Sherpa Kitten Nano packaged model](https://k2-fsa.github.io/sherpa/onnx/tts/all/English/kitten-nano-en-v0_8-int8.html)
- [Piper Python speech API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md)
- [Published Piper Amy Low model](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/amy/low)
