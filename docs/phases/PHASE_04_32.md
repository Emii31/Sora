# Phase 4.32 — Motorola Liquid CPU comparison

Starting checkpoint: `19ca2f54e357e2f6cff559ef4a3226012f004489`. On 2026-11-21, compared thread counts and CPU placement on the Motorola with the existing phone binary and the selected Liquid voice. The phone reports maximum frequencies of 1.8048 GHz on cores 0–3 and 2.208 GHz on cores 4–7.

The benchmark compares four threads on cores 4–7, three on cores 5–7, and six on cores 0–1 and 4–7. The settings apply to the owned runner process. Each profile sets both generation and prompt-processing thread counts. Model files, quantization, random seed, synthesis context, source text and the 0.5-second playback reserve are shared. The runner checks the selected affinity before measurement and reapplies it during the session. Android scheduling can still vary between trials.

Two short rounds reverse the profile order. Identical PCM hashes are required before a candidate advances to the longer fixture. Each trial starts a fresh phone runner. The virtual monitor uses the Phase 4.31 calibration and captures synthetic speech. Throughput includes speech-model prefill and local transport. Chat generation, microphone timing and physical speakers are outside the benchmark.

```bash
cd /mnt/data/Companion/Miru
PYTHONPATH=. .venv/bin/python -B scripts/benchmark_phone_cpu.py \
  --kit /mnt/data/Companion/sora-liquid-audition \
  --report /tmp/sora-phone-cpu-432
```

The report directory must be fresh. NumPy comes from the existing optional diagnostics requirements. No package installation was needed for this phase. Raw monitor WAVs and runner logs are kept in the external recovery directory. The Git evidence contains the synthetic summary.

## CPU placement results

The first pilot stopped when Android reported mask `63` after a request for `f3`. The rerun retained the effective mask at both ends of every trial and excluded candidates with a mismatch from longer confirmation. These are snapshots of the runner's main thread. They cannot prove that the mask stayed fixed throughout inference.

| Round | Profile | Observed masks | Wall seconds per audio second | Added monitor time |
| --- | --- | --- | ---: | ---: |
| First | Four fast cores | f0, f0 | 4.29 | 6.33 s |
| First | Three fast cores | a0, 80 | 1.74 | 0.73 s |
| First | Six mixed cores | c3, 93 | 3.64 | 3.97 s |
| Reverse | Six mixed cores | c3, f3 | 9.34 | Inconclusive |
| Reverse | Three fast cores | e0, e0 | 2.03 | 1.60 s |
| Reverse | Four fast cores | d0, f0 | 1.90 | 1.45 s |

All six short clips have the same PCM hash as the Phase 4.31 reference. Neither alternative held its requested mask at both checkpoints in both rounds. These measurements do not isolate an effect of changing CPU placement.

The follow-up used `--candidate three-wide` to keep mask `f0` for both thread counts. The candidate is eligible for the longer test only if both short outputs match the baseline PCM and both affinity snapshots match the request.

Targeted tests covered CPU argument validation, default runner configuration, waveform alignment, Liquid playback, continuous speech, voice context and the local chat provider. They returned 104 passes. Python compilation and whitespace checks passed. Playback calibration reported zero added time for both clean cases and about 0.57 seconds for the delayed producer.

## Same-mask follow-up

The four short runs all reported `f0` both before and after measurement. The median wall time was 1.99 seconds per second of speech for both thread counts, rounded to two decimal places. Each two-trial group won one round. There was no consistent short-reply advantage.

| Round | Threads | Wall seconds per audio second | Added monitor time |
| --- | ---: | ---: | ---: |
| First | 4 | 1.91 | 1.25 s |
| First | 3 | 1.96 | 1.40 s |
| Reverse | 3 | 2.01 | 1.71 s |
| Reverse | 4 | 2.07 | 1.92 s |

Repeat the same-mask comparison by adding `--candidate three-wide` to the benchmark command and using a fresh report path.

The 10.86-second confirmation clip took 19.00 seconds to generate on three threads (1.75 seconds per audio second), and 19.59 seconds on four threads (1.80). The three-thread mask snapshots matched `f0`. The four-thread case observed `c0` and `20`, so this pair cannot isolate thread count. Both clips matched the Phase 4.31 long PCM hash. The monitor could not confidently align either long recording. The short trials with the same mask all showed measurable added monitor time.

Keep the four-thread runtime default. The settings tested here did not sustain playback speed, and the modest timing differences do not justify adopting a new configuration. The next phase can measure time separately in the speech backbone, audio decoder and vocoder, then target the biggest cost with the current weights.

The completed comparisons include ten short runs and two long runs. Synthetic summaries are under `docs/verification/phase_04_32/`. Cleanup checks confirmed removal of the runner lock, USB forward and virtual sinks. No CPU governor or global Android scheduling settings were changed.

The exact regression command used the existing environment:

```bash
PYTHONPATH=. .venv/bin/python -B -m pytest tests/test_liquid_phone_cpu.py \
  tests/test_voice_playback_diagnostics.py tests/test_liquid_live.py \
  tests/test_voice_continuous.py tests/test_voice_context.py tests/test_voice_brain.py -q
```
