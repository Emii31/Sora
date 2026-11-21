# Phase 4.42 — Gwen live speech on Motorola

The owner chose to continue with Gwen after the Phase 4.41 comparison. This phase keeps the Scylla’s Band v2 LiteRT voice, weights, four Euler steps, default pace and delivery controls. It limits later synthesis chunks to 256 latent frames and keeps a private speech process warm. The worker primes both a short and a multi-sentence turn before it reports readiness. The new tools are standalone. The existing Sora voice and app entry points are unchanged.

## Results

- The stock mobile profile needed 1.51 s to begin the 12 s fixture without gaps in a PCM playback simulation. The 256-frame profile needed 0.78 s. Total synthesis rose from about 3.05 s to 3.69 s on that fixture, with more audio ready sooner.
- With a fixed seed, eight new Motorola requests in four styles, containing about 3.6–9.5 s of speech, all met the 1.2 s text-to-audible-start target. Measured startup was 0.63–1.01 s at the native producer. Playback was simulated using native PCM callbacks and the first audible sample.
- The persistent worker was verified over USB with fresh random seeds, including rejection of a malformed request followed by successful audio. After a 3.59–4.14 s one-time warmup, all 16 turns across two sessions met the target. Estimated uninterrupted audible start was 0.62–1.19 s after sending the text, median 0.70 s. The USB report timestamps complete PCM chunks at the client and estimates how early playback could begin without running out of samples. [Timings](../verification/phase_04_42/timings.json)
- Local Whisper tiny.en made one word-level edit in 165 words with each profile. The voiced sample is about 37 seconds and plays playful, tender, sad and angry. It uses PCM generated on the phone and inserts short silent breaks.
- The i5-7300U missed the live speech target in the stock, 160-frame and 192-frame tests. The phone can act as an offline USB speech worker for the laptop. These checks cover the speech stage. End-to-end microphone, model response and actual speaker continuity remain pending.

## Reproduction and handoff

Source checkout: Scylla’s Band native commit `24ffd0290e278b6bd457ae630c4eafb428d2e23f`. Model snapshot: `c12adda85f566f9206c404ebb23bf0adaf577de4`. LiteRT: 2.2.0. All model/runtime assets were prepared in Phase 4.41.

1. Run `python3 scripts/prepare_gwen_manifest.py ORIGINAL_MANIFEST NEW_MANIFEST` and place the new manifest in the profile directory alongside links to the same `assets` and `litert` directories.
2. Compile `scripts/gwen_stream.cpp` with C++17, the pinned native runtime’s include directory and `-lscyllasband_native`. The Android build used NDK Clang for arm64 API 26, `-O2 -static-libstdc++ -Wall -Wextra -Werror`. Put `libscyllasband_native.so` and `libLiteRt.so` on the worker’s library path.
3. Start `gwen-stream PROFILE_DIR`. Wait for the line `ready`. Each request is one UTF-8 line containing delivery settings, a tab, then text. Each `pcm RATE BYTES` header is followed by that number of signed 16-bit little-endian mono PCM bytes. `done` ends the turn. `error` discards the turn. Use a raw pipe, such as `adb shell -T`. The child uses no network listener.
4. Local verification workspace is `/mnt/data/Companion/recovery/phase_04_42`. It contains the synthetic fixtures, `benchmark-phone.sh`, `verify_stream.py`, run logs and `gwen-live-motorola.wav`. Raw model weights and audio remain outside Git.

[Model snapshot](https://huggingface.co/spybyscript/scyllasband/tree/v2-20261020-litert) · [Pinned native runtime](https://github.com/lowkeytea/scyllasband/tree/24ffd0290e278b6bd457ae630c4eafb428d2e23f)
