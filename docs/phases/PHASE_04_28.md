# Phase 4.28 — Voice Startup and Playback Latency Controls

## Status

Verified within the terminal prototype's bounds on 2026-11-20. Starting checkpoint: `e7cfccf5ce8261322dcd2b6dde81f5a47f902f36`. Two-second live conversation remains unachieved. No app UI, new voice provider, model download, global dependency change or autostart was introduced.

## Changes

1. Removed repeated voice-only prompt instructions. Configured name, personality/speech excerpts, saved identity facts, core-memory budgets, recent history, AI honesty and user-boundary rules remain. The text-chat default is unchanged. In the synthetic fixture, the voice system prompt decreased from 1,850 to 1,533 UTF-8 bytes (17%). A three-question alternating-order local model comparison is recorded, but reply lengths and cache states differed; its timings are not a definitive aggregate speedup.
2. Added a one-token local chat warmup before the terminal announces Listening. It uses the account's real context and saves no conversation. Cold load/prefill is reported as startup time, not removed from accounting. Normal inference still rejects truncated replies; only the explicit warmup accepts a length finish. `--no-warmup` disables this step. Idle model eviction and subsequent reloads remain possible.
3. Added first-token and brain-ready timing, chosen buffer and playback-policy fields to turn reports. Explicit `--report` also saves `startup.json` with the warmup duration; normal runs still discard temporary server logs.
4. Automatic buffering uses 0.5 seconds only for replies of at most 64 UTF-8 bytes and 8 whitespace-separated words. Other replies retain the previous 1.5-second streaming reserve. Explicit `--buffer-seconds` overrides automatic selection, including zero.
5. Added optional `--smooth-long-replies`: replies above 100 UTF-8 bytes or 16 words wait for complete audio before playback. This prevents waiting for further generated chunks during playback but adds substantial start delay. It is intentionally not the default. Full buffering is bounded to 30 seconds of PCM and remains cancellable.
6. Added a reproducible fixed-sentence playback comparison script and extended the existing disposable context verification with warmup reporting. Neither script edits production user data or credentials.

## Run

Keep the existing loopback Ollama service running with the installed `qwen2.5:1.5b-instruct` model. Connect and authorize the Motorola. The pinned patched Liquid runner and models from Phase 4.27 are still required.

```bash
cd /mnt/data/Companion/Miru
PYTHONPATH=. .venv/bin/python -B scripts/live_liquid_voice.py \
  --kit /mnt/data/Companion/sora-liquid-audition \
  --vosk-model /home/imam/Projects/openwakeword-train/model/en/vosk-model-small-en-us-0.15
```

Wait for Listening. Enter interrupts, `q` + Enter exits. Add `--smooth-long-replies` only if you prefer waiting for an entire long reply over streamed playback. `--buffer-seconds 1.5` restores fixed buffering for every reply and overrides that option. Audio model, interleaved mode, forced text protocol, sample rate and speech PCM are unchanged.

## Real model/device results

After explicitly unloading the owned test model, cold warmup took **16.85 seconds**, with history still empty. Four synthetic recognized-input turns then passed identity, saved tea preference, new plant acknowledgement and persisted Juniper recall using the local brain, real Motorola inference, PipeWire playback and saved history:

| Input | Brain ready | Playback starts | Estimated gaps |
| --- | ---: | ---: | ---: |
| Name | 3.50 s | 7.03 s | 0 |
| Saved tea | 2.01 s | 3.88 s | 0 |
| New plant fact | 3.77 s | 6.67 s | 0 |
| Restart recall | 5.34 s | 7.13 s | 0 |

These times begin after recognition, exclude speech duration and the roughly 900 ms endpoint pause, and measure writing into the playback pipe rather than physical sound arrival. They should not be presented as a matched end-to-end percentage improvement over Phase 4.27, whose model/cache states and replies differed.

Repeated identical short-sentence probes started playback about 0.66–1.04 seconds earlier with the smaller buffer. Initial probes had zero estimated gaps; one later short probe had one. There is no universal gap-free streaming guarantee. In the final fixed-sentence comparison, short playback was 2.51 s with the old reserve versus 1.53 s with the small reserve.

A four-second reserve for the longer sentence performed inconsistently (one run reported ten estimated gaps), so it was rejected. Complete buffering of the 11.82-second long sample started at **17.32 s**, finished at 29.24 s and reported no generation waiting during playback. The same sample streamed with a fixed reserve started at 3.11 s and reported two estimated gaps. This large delay is why smooth-long mode is opt-in. Pipe-write-based gap estimates do not establish audible artifact counts.

For each sentence, raw generated PCM SHA-256 hashes matched across buffer modes. These tests therefore changed playback timing, not the voice waveform. Perceptual quality and physical acoustic timing still require owner review.

The actual CLI entry point was also run with disposable data and a prerecorded WAV, real Vosk recognition, startup prefill, phone generation and playback. It exited 0, wrote startup/turn reports and saved exactly one exchange. Warmup was 14.17 s and playback began 5.99 s after recognition. Vosk transcribed the test's "You named your plant Juniper" as "you and plant juniper", and the reply discussed the plant rather than the intended naming statement. This verifies plumbing, not reliable recognition or intent understanding. No new human microphone trial was performed.

## Commands and evidence

```bash
PYTHONPATH=. .venv/bin/python -B scripts/verify_live_voice_context.py \
  --kit /mnt/data/Companion/sora-liquid-audition --report /tmp/sora-context-428
PYTHONPATH=. .venv/bin/python -B scripts/benchmark_voice_playback.py \
  --kit /mnt/data/Companion/sora-liquid-audition --report /tmp/sora-playback-428
```

Both report destinations must be fresh. The benchmark's final script labels the optional complete-audio comparison `smooth_long`; the earlier recorded experiment used `automatic` while that behavior was being evaluated. The final default remains streaming.

Targeted regression command:

```bash
PYTHONPATH=. .venv/bin/python -B -m pytest \
  tests/test_voice_brain.py tests/test_voice_context.py tests/test_fast_local_chat.py \
  tests/test_chat_archive_and_consolidate.py tests/test_chat_range_query.py \
  tests/test_onboarding_persistence.py tests/test_local_single_device_mode.py \
  tests/test_liquid_live.py tests/test_voice_input.py -q
```

Result: **146 passed, 7 skipped, 2 warnings**, exit 0. The warnings are the existing tuple-returning legacy wrappers; the standalone suite's earlier limitations remain as recorded in Phase 4.27. It was not rerun against production data. New coverage includes account-context warmup without history writes, one-token truncation boundaries, first-token metrics, automatic buffering, explicit zero override, complete-audio cancellation, waiting until generation completes and the PCM size bound. Python compilation and CLI help also passed.

Canonical synthetic evidence is in `docs/verification/phase_04_28/`. Pre-edit backups and extra experiment scripts/logs are under `/mnt/data/Companion/recovery/phase_04_28/`, excluded from Git. No raw human recording, credentials or private memory is published.

## Handoff

Startup prefill and short-reply buffering are implemented and verified; longer smooth playback is an explicit latency/continuity tradeoff. Remaining issues are variable prefill/generation time, streamed playback starvation, recognition mistakes and pending subjective delivery review. Proposed Phase 4.29 is to investigate beginning speech from validated sentence boundaries while the local brain is still generating, without saving incomplete turns or substituting the selected voice. Consistent two-second responses must be measured, not assumed. App integration remains deferred.
