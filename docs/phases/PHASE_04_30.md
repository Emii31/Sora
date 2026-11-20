# Phase 4.30 — Continuous Speech Context

## Outcome

Verified as an **optional terminal prototype** on 2026-11-20, starting from `a1c2dd28600da821202ed9c339d0e7d55964a014`. One Liquid inference session now accepts incremental reply text while the local chat model continues generating. The selected weights, interleaved voice mode and audio sampling are retained. Whole-reply mode remains the default; subjective delivery approval, reliable playback continuity and consistent two-second conversation are still pending.

The important improvement over Phase 4.29 is observed PCM parity: with identical actor context and completed text, continuous input generated exactly the same audio bytes as whole-text input in the tested cases. It did not create the previous sentence-reset duration inflation. This establishes parity for those fixtures, not general speech fidelity or perceptual quality.

## Design

- The private native runner accepts `speech_input_id` on its existing streaming completion route. The input is updated through `POST /v1/speech-input/<id>` and cancelled through DELETE. IDs are unpredictable per-turn values. Only one continuous input session is registered at a time; inference still has one worker.
- A ready SSE event establishes registration before updates begin. HTTP uses three bounded handler threads so the open audio response cannot block input/cancel controls. The first prototype timed out with the original one-thread HTTP pool; the corrected transport passed live tests.
- Native input is cumulative and append-only, bounded to 2,000 UTF-8 bytes, with an explicit final flag. Empty initial finalization, oversized input, duplicate sessions, updates after finalization, missing text/audio modalities and invalid generation budgets are rejected. Continuous requests use a fresh context and at most 512 generation steps. An input wait times out after 30 seconds without an update. Completed/aborted jobs release their registered input.
- The native tokenizer releases only complete whitespace-delimited prefixes before finalization. This prevents a later suffix from changing a previously accepted partial word's BPE tokens. Accepted token prefixes are checked and a mismatch fails the request rather than silently changing speech. Text without whitespace may wait until finalization. One backbone/vocoder context continues through the whole reply; only finalization appends text-end.
- `voice_continuous.py` owns the input ID, ready/closed state, acknowledged text and control connections. It rejects oversized or finalized input and cancels only its own ID. After cancellation, an old native job can briefly retain its slot during prefill; the continuous stream retries an explicit HTTP 409 for at most three seconds. It does not retry unrelated modes or generation errors. This fixed a recovery failure found in the first real cancellation run.
- `VoiceTurn` starts one audio reader and feeds small coalesced text updates from `LocalVoiceBrain`'s raw-text callback. Leading/trailing whitespace is held or stripped consistently with the completed reply; internal text is preserved. The speech context is the original user message, without a repeated reading instruction. A complete validated brain reply, matching speech text and finished playback are all required before saving one exchange.
- Provider failure or user interruption can leave a partial answer already heard, but no partial exchange is saved. The existing output audio limit and coordinated worker cleanup remain. This mode is mutually exclusive with sentence streaming and complete-long-reply playback.

No model downloads, global dependency changes, app UI, microphone activation, autostart or remote inference were introduced. Implementation and the private dependency patch were performed locally through Codex; no dependency upstream contribution was made.

## Run

The current local kit was rebuilt and its source patch is recorded in the repository. The launcher checks the runner's `continuous_text` health capability and updates the phone cache by hash. Build using the existing pinned source/SDK:

```bash
cd /mnt/data/Companion/Miru
bash scripts/build_liquid_voice_runner.sh /mnt/data/Companion/sora-liquid-audition
```

Start the existing Ollama service separately if necessary (`OLLAMA_HOST=127.0.0.1:11434 ollama serve`). The installed chat model remains `qwen2.5:1.5b-instruct`. With the Motorola authorized over USB:

```bash
PYTHONPATH=. .venv/bin/python -B scripts/live_liquid_voice.py \
  --kit /mnt/data/Companion/sora-liquid-audition \
  --vosk-model /home/imam/Projects/openwakeword-train/model/en/vosk-model-small-en-us-0.15 \
  --continuous-speech
```

Omit the last option for the unchanged default. Enter interrupts; `q` + Enter exits. Warmup still occurs before Listening. An explicitly requested `--report` retains text-bearing diagnostics; normal temporary logs are removed on exit. No voice-operated device tools or acoustic speech-to-interrupt were added.

## Matched brain/phone/playback comparison

Two alternating-order pairs used identical requested/completed text, exact prompt prefill outside timing, fresh disposable history, the same 0.5-second playback reserve and identical actor context. The helper overrides the baseline actor context solely for this comparison; it does not change production whole-reply defaults.

| Pair | Whole starts | Continuous starts | Whole finishes | Continuous finishes |
| --- | ---: | ---: | ---: | ---: |
| 0 | 5.07 s | 2.87 s | 16.47 s | 13.35 s |
| 1 | 6.46 s | 2.46 s | 15.87 s | 12.56 s |

Continuous playback began before brain completion in both pairs. All four generated clips were 7.02 seconds long and had the same PCM SHA-256 hash. Unlike the previous sentence experiment, no additional waveform repetition or duration was introduced relative to the matched whole-context output. A small fixed fixture with two repetitions is not a general performance or fidelity guarantee.

Playback starvation remains: continuous runs reported 12 and 10 estimated gaps; whole runs reported 19 and 4. These are pipe-write estimates, not acoustic measurements. WAVs concatenate generated PCM and do not encode extra wall-time starvation. Timing starts after recognition and excludes startup, speech duration, the approximately 900 ms endpoint pause and acoustic output latency. The experiment does **not** establish two-second end-of-speech conversation.

## Other real-device checks

- Four actual local-brain/phone/playback checks passed configured Sora identity, saved jasmine-tea preference, new Juniper acknowledgement and restart recall. Playback starts were 3.26/2.75/3.19/5.59 s, with estimated gaps still present. Inputs were synthetic recognized text; no new human microphone trial occurred.
- Native protocol checks returned unknown input 404, oversized update 400, empty finalization 400, duplicate session 409 and post-final update 409. The rejected updates did not alter the subsequent speech waveform. Whole and deliberately fragmented input produced identical 10.86-second audio hashes.
- The previously failing line, "Juniper is a great name for a plant, Alex!", completed under its natural conversational context in both whole and continuous tests, with identical 3.74-second PCM output. This is an observed regression check, not a promise that the model never fails on other utterances.
- Initial immediate recovery returned HTTP 409 because native cleanup lagged client shutdown. After the bounded busy retry, actual reasoning cancellation took 0.092 s and playback cancellation 0.178 s, with neither saving messages. A subsequent completed turn saved exactly one exchange. These are client-worker stop times, not complete native prefill-abort or acoustic mute measurements.

## Reproduce and evidence

Use fresh report directories:

```bash
PYTHONPATH=. .venv/bin/python -B scripts/verify_continuous_runner.py \
  --kit /mnt/data/Companion/sora-liquid-audition --report /tmp/sora-native-430
PYTHONPATH=. .venv/bin/python -B scripts/verify_live_voice_context.py \
  --continuous-speech --kit /mnt/data/Companion/sora-liquid-audition --report /tmp/sora-memory-430
PYTHONPATH=. .venv/bin/python -B scripts/benchmark_voice_sentences.py \
  --continuous-speech --save-audio --kit /mnt/data/Companion/sora-liquid-audition --report /tmp/sora-comparison-430
```

The native verifier also accepts `--text` and `--context` for synthetic regression fixtures. It verifies control guards and exact PCM parity without opening a microphone or playing audio. The other two scripts exercise real laptop playback with disposable data established before application imports.

Canonical evidence is under `docs/verification/phase_04_30/`. Extra attempts, pre-edit backups, logs and synthetic WAVs remain outside Git under `/mnt/data/Companion/recovery/phase_04_30/`. Real credentials, user memory, model weights, raw human recordings and recovery dumps are excluded from publication.

## Automated/native verification

```bash
PYTHONPATH=. .venv/bin/python -B -m pytest \
  tests/test_voice_continuous.py tests/test_voice_sentences.py tests/test_voice_brain.py \
  tests/test_voice_context.py tests/test_fast_local_chat.py tests/test_chat_archive_and_consolidate.py \
  tests/test_chat_range_query.py tests/test_onboarding_persistence.py \
  tests/test_local_single_device_mode.py tests/test_liquid_live.py tests/test_voice_input.py -q
```

Result: **188 passed, 7 skipped, 2 existing legacy return-value warnings**, exit 0. Coverage includes raw Unicode callbacks, canonical whitespace, early playback, finalized/oversized input, consumer/provider failure, no partial saves, owned cancellation, session-ready events, bounded busy retry and mode constraints. The prior standalone legacy-suite limitations remain; full-suite success is not claimed.

The existing Android CMake target rebuilt successfully. Clean pinned-source patch reconstruction and reverse-check reproduce all four built source files. Python compilation and CLI help passed. Project Python remains the existing `.venv` 3.11.18; no interpreter replacement was performed.

## Handoff

Continuous context is a useful optional backend improvement and preserves the matched whole-context waveform in the tested cases. Keep the default unchanged until subjective listening and real conversation checks pass. Proposed Phase 4.31: measure actual playback continuity separately from pipe-write estimates, profile phone generation/underruns, and tune the remaining delay. Recognition accuracy, voice wake-up and app work remain deferred. Do not promote a mode solely because its first audio arrives earlier.
