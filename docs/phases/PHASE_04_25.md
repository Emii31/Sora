# Phase 4.25 — Liquid Audio on the Owner's Android Phone

## Status

Verified as a standalone phone inference benchmark. The owner authorized this test after connecting the phone by USB.

## Device and model

ADB identified a Motorola moto g stylus 5G (2024), Snapdragon SM6450, ARM64, Android 16/API 36, with 7,633,392 kB total RAM. Available memory before inference was about 2.6 GB. CPU cores 4–7 have the highest reported capacity. Battery temperature before the test was 35 degrees Celsius while charging over USB.

The same four Q4_0 GGUF files from the approved Liquid LFM2.5-Audio-1.5B chat voice were copied to `/data/local/tmp/sora-liquid-phase-425`. Their SHA-256 hashes matched the laptop files. A failed initial transfer was retried successfully after the owner reconnected the USB cable. This test uses a standalone server in that directory.

## Build and measurement method

The runner source is pinned to llama.cpp `ec9d1fdd9cc18643c5e161b65b8053f6f6f34a4b`, matching Phase 4.24. The Android NDK is 27.3.13750724. The build targets ARM64/API 28 with `armv8.2-a+dotprod+fp16`, which matches CPU features read from the phone. CPU repacking is enabled, and the build uses static C++ libraries, four threads, and a 2,048-token context.

The first run inherited a `taskset f0` launch mask, but the runner subsequently expanded its affinity. A repeated warmup slowed substantially. Inspection found three worker threads restricted to cores 4 and 7. Applying `taskset -ap f0` to all runner threads restored their access to cores 4–7. The final coordinator supplies both `--cpu-mask f0` and `--cpu-mask-batch f0`, reapplies the process-wide mask after loading, and records each startup thread's allowed CPUs. Warmup is excluded from per-reply timings, so this incident must be considered separately from the fast measured turns.

The benchmark server binds to the phone's loopback address. An ADB USB forward makes it accessible to the laptop's timing harness. The model and audio decoder run on the phone CPU. The default interleaved chat prompt and the three prerecorded fixtures are the same as the laptop test. Each fixture is submitted as audio and as the saved Vosk transcript from the laptop baseline, with alternating input order and an untimed warmup. Text timing excludes speech recognition. It does not measure a live microphone, endpoint detection, speaker playback, or interruptions.

`scripts/benchmark_liquid_android.py` reuses the existing Liquid stream decoder and timing calculations. It records first voiced chunk, estimated smooth audible start, reply duration, and total elapsed time. Synthetic checks verified input order, exact transcript reuse, six saved outputs, warmup, and protection against overwriting earlier timing results.

## Results

Three runs completed with 18 replies. Across all runs, median first voiced chunks were 1.15 seconds for text input and 2.07 seconds for direct audio input. The final run started with verified CPU affinity after the placement correction.

| Input path | Median smooth start across three runs | Range across three runs | Final-run median smooth start |
| --- | ---: | ---: | ---: |
| Saved transcript | 2.49 s | 1.43–4.57 s | 3.63 s |
| Recorded speech | 3.20 s | 2.51–4.03 s | 3.18 s |

The phone was faster than the laptop measurements in Phase 4.24. Only the short check-in text replies met the two-second smooth-start target. The longer text response took 3.89–4.57 seconds before estimated smooth audible playback. These three short runs do not establish all-day thermal or battery performance. Battery temperature readings before and after the repeated tests were 34 and 35 degrees Celsius while USB charging. The initial slow repeat warmup was corrected before its measured turns, and the final run confirmed the improved timings after an independent restart.

All 18 WAVs passed channel, PCM format, sample-rate, non-silence and duration checks. None had samples within one PCM unit of full scale. The transcript-based check-in generated an unsupported statement about a webcam, showing a response-quality issue. The test supplied only prerecorded audio and text. The standalone runner used the same minimal benchmark system prompt as the laptop and did not exercise Sora's memory, persona, or application chat pipeline.

The benchmark processes stopped and their ADB forwards were removed. The temporary phone directory and approximately 1.07 GB of model files were removed after verification. The Android source, build, and license remain in the laptop's local model kit for another test.

## Reproduction and evidence

The source and build script are under `/mnt/data/Companion/sora-liquid-audition/android/`. The build command is `bash /mnt/data/Companion/sora-liquid-audition/android/build-android.sh`. Start the runner with the same four GGUF files on the phone, bind it to `127.0.0.1:18080`, and apply the affinity correction after model initialization. A laptop ADB forward provides the harness endpoint.

```bash
adb forward tcp:18081 tcp:18080
PYTHONPATH=. .venv/bin/python -B scripts/benchmark_liquid_android.py \
  --endpoint http://127.0.0.1:18081/v1/chat/completions \
  --transcripts "$baseline" --output "$result_dir" \
  "$fixtures"/input-{check-in,good-news,comfort}.wav
```

Committed evidence is under `docs/verification/phase_04_25/`. The conversation artifacts under `sora-liquid-audition/android-comparison/` include `run-phone.py`, build logs, hashes, per-run logs, timing data, and all 18 WAVs. Both the ARM64 build and the three benchmark runs exited 0. The harness synthetic checks passed. History prefix checks against `f2e5127` and whitespace checks passed.

## Next action

Use the phone as the candidate host for a live conversation prototype. That phase needs real microphone endpoint detection, buffered playback, interruption handling and measurement through the actual Sora context pipeline. The two-second goal remains unmet for most measured replies.
