# Phase 4.31 — Playback continuity and phone throughput

On 2026-11-21, measured fixed synthetic speech from the connected Motorola through Sora's normal playback writer into a dedicated PipeWire virtual sink. The monitor records only the test signal. Metrics describe digital output and phone generation, with physical speakers and microphone outside this measurement.

The diagnostic aligns audible parts of generated PCM to the monitor recording by waveform correlation. It compares the change in offset between early and late matched sections, so leading buffering and pauses already in the model's waveform do not count as added playback time. Low confidence, missing endpoints and inconsistent alignment are reported as inconclusive. A short symmetric filter reduces sensitivity to fractional-sample resampling. Calibration verified two clean cases, including preloaded 20 ms chunks, and detected approximately 0.53 seconds of added time when the producer deliberately paused.

Phone profiling sends the complete fixture text through the continuous speech transport at the start of the test. It measures speech generation separately from chat-model latency. The script records chunk arrivals, time blocked handing chunks to playback, runner CPU time and sampled thermal metadata. Generation wall time divided by audio duration measures how much real time is required to produce one second of PCM. Values above 1 indicate that a finite startup reserve can eventually run out.

Run from the repository root with the Motorola authorized over USB. The project virtual environment has the optional diagnostics dependency installed. A new environment can install it using the pinned requirements file. Normal playback does not import NumPy.

```bash
.venv/bin/python -m pip install -r requirements/voice_diagnostics.txt
PYTHONPATH=. .venv/bin/python -B scripts/profile_voice_playback.py \
  --kit /mnt/data/Companion/sora-liquid-audition \
  --report /tmp/sora-playback-431 --include-full-buffer
```

Use a fresh report directory. Add `--calibration-only` for a hardware-independent check of synthetic playback through the local audio server. The full report includes WAVs, waveform anchors and chunk traces. The Git evidence contains only synthetic summary results. Private logs and WAVs remain under `/mnt/data/Companion/recovery/phase_04_31/`.

Automated checks cover known inserted delay, fixed offsets, gain changes, intentional source silence and missing/clipped capture. The targeted pytest command ran the diagnostics, Liquid playback, continuous speech, voice context and local brain test modules, with 96 passes. Python compilation and virtual environment dependency consistency passed. Phase 4.30 remains the reference for whole-conversation testing.

## Measured results

| Run | Fixture | Startup reserve | Phone seconds per audio second | Start of pipe write | Added monitor time between anchors |
| --- | --- | ---: | ---: | ---: | ---: |
| Initial | 3.74 s | 0.5 s | 1.67 | 1.35 s | 0.92 s |
| Initial | 3.74 s | 1.5 s | 1.86 | 3.71 s | 0.00 s |
| Initial | 10.86 s | 0.5 s | 1.49 | 1.38 s | Inconclusive |
| Initial | 10.86 s | 1.5 s | 1.51 | 2.95 s | Inconclusive |
| Repeat | 3.74 s | 0.5 s | 4.66 | 5.52 s | 5.34 s |
| Repeat | 3.74 s | 1.5 s | 3.03 | 5.37 s | 1.48 s |
| Repeat | 10.86 s | 0.5 s | 2.72 | 2.14 s | Inconclusive |
| Repeat | 10.86 s | 1.5 s | 3.06 | 4.86 s | Inconclusive |
| Repeat | 10.86 s | Full | 1.93 | 20.97 s | 0.00 s |

Both fixtures produced identical reference PCM hashes across runs and reserves. Dispatch to the playback queue blocked for less than 1 ms in every run. After the first audio chunk, the phone and transport still took 1.42–3.78 seconds per second of generated audio. Runner CPU time averaged 3.0–3.8 cores during the generation interval. Native logs report 1.18–6.18 seconds of prompt evaluation and 2.89–18.58 seconds of backbone decode. These counters cover parts of the native pipeline. The measurements do not isolate the separate vocoder cost.

The repeat run was much slower despite sampled Android thermal status 0. Those snapshots cannot rule out scheduling or frequency changes between samples. Buffer trials were sequential and the device speed varied. The observations establish that the tested configuration delivered PCM slower than playback at the measured rates, but do not establish a causal ranking of the two fixed reserves. The short monitor recordings confirm real added playback time. Alignment rejected the streamed long recordings because coverage or endpoint confidence was insufficient. Their pipe-estimated gap counts remain diagnostic only.

The full-buffer control measured no added time between matched anchors at a roughly 21-second wait. Keep the current playback defaults. The next phase should benchmark alternative inference execution settings on the same voice model and matched PCM fixtures, with phone throughput and monitor continuity as acceptance criteria.

The original unfiltered alignment missed speech anchors on several fixtures. The symmetric filter recovered valid short matches while retaining the confidence thresholds, with the streamed long captures still inconclusive. Raw capture and timestamps remain available for further analysis. Source scan, append-only history and whitespace checks passed.

Exact targeted command:

```bash
PYTHONPATH=. .venv/bin/python -B -m pytest tests/test_voice_playback_diagnostics.py \
  tests/test_liquid_live.py tests/test_voice_continuous.py tests/test_voice_context.py \
  tests/test_voice_brain.py -q
```
