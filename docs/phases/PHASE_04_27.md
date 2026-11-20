# Phase 4.27 — Sora Persona and Memory in Live Voice

## Status and scope

Verified as a local terminal integration on 2026-11-20. Starting checkpoint: `a51890e0eb946b2a649825da66ac8fda62306a3f`. This phase connects the active character, saved identity, bounded core-memory excerpts and recent chat to the microphone prototype. It does not implement wake words, phone-native microphone capture, acoustic echo cancellation or app UI integration.

Direct Liquid chat did not reliably recall supplied first-person facts. The implemented path instead uses the configured local chat model to compose a grounded reply, then forces those text tokens through the selected Liquid interleaved chat voice. The audio generator retains its original minimal interleaved system prompt and audio sampling path. This preserves the selected model/mode, but does not establish perceptual equivalence for every sentence or an ElevenLabs-quality claim.

## Components

- `voice_context.py` selects the sole active account, or requires `--user-id` when several exist. With no registered accounts it uses the existing legacy root data, without migrating it. Each turn reloads the configured character, reads core memory and recent chat, and scopes all reads/writes to that account. A deleted/inactive account or a changed legacy/account configuration blocks continuation.
- `prompt.py` adds an opt-in voice variant to the compact chat prompt. The existing text-chat default remains unchanged. Voice adds conversational identity, bounded saved identity facts and short spoken-reply guidance, while keeping screen/camera inactive.
- `voice_brain.py` snapshots the model, endpoint and credential under the provider lock. It makes a cancellable loopback-only streaming completion with no discovery, remote fallback or device tools. Empty, truncated and failed responses are rejected.
- `storage.py` saves a completed user/assistant pair atomically and idempotently in the existing chat history. Thread/process locks coordinate the append and archive helpers; reminder migration also holds the chat transaction. Cancellation, provider failure and mismatched speech text do not save an exchange. This is shared recent history and access to existing core memory, not a new autonomous memory-extraction pipeline.
- `patches/liquid-forced-speech.patch` extends the pinned private runner with optional `spoken_text` and a health capability. It forces ordinary text tokens while allowing the model to generate audio frames, then uses the model's text-end token to finish audio. Token-budget exhaustion is an error. The corrected implementation removes an extraneous leading newline and preserves the token variable's lifetime across decode iterations. Initial longer probes stalled before these corrections.
- `scripts/build_liquid_voice_runner.sh` checks the pinned source commit, applies the patch only if cleanly applicable (or already applied), and invokes the existing isolated Android build. No dependency upstream is modified remotely.

## Run locally

The installed model is `qwen2.5:1.5b-instruct`. The previous local chat configuration named unavailable `llama3`; this phase changed only its model selection, preserving its endpoint and credential. A private configuration backup is outside Git in the phase recovery directory. Ollama and all model files remain outside the repository.

Start the existing local service if it is not running, in a separate terminal:

```bash
OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

With USB debugging authorized on the Motorola, build the private runner once:

```bash
cd /mnt/data/Companion/Miru
bash scripts/build_liquid_voice_runner.sh /mnt/data/Companion/sora-liquid-audition
```

The builder uses the already installed SDK/NDK paths in the local kit script. Source is pinned to `ec9d1fdd9cc18643c5e161b65b8053f6f6f34a4b`. It does not download compilers or weights. The launcher checks and updates the phone's cached runner by hash.

```bash
cd /mnt/data/Companion/Miru
PYTHONPATH=. .venv/bin/python -B scripts/live_liquid_voice.py \
  --kit /mnt/data/Companion/sora-liquid-audition \
  --vosk-model /home/imam/Projects/openwakeword-train/model/en/vosk-model-small-en-us-0.15
```

Speak after Listening; pause to submit. Enter interrupts and listens again. `q` + Enter exits. The recognizer is required for this context pipeline. Normal runs discard temporary server logs; an explicitly requested fresh `--report` directory retains diagnostics that can contain conversation text. Completed voice exchanges are intentionally saved in Sora's existing history.

## Real model and device verification

Four synthetic recognized inputs exercised the local Qwen brain, real Motorola Liquid inference, laptop PipeWire playback and saved history. These were not a new human microphone trial. A fresh context adapter was created for every turn. Results in `docs/verification/phase_04_27/live_results.json`:

| Input | Verified reply content | Playback starts after recognized input |
| --- | --- | --- |
| Name | "I'm Sora" | 23.17 s (initial cold turn) |
| Saved tea preference | "You like jasmine tea" | 6.42 s |
| New plant fact | Responded to the Juniper fact; exchange saved | 9.05 s |
| Recall after context restart | "You named your plant Juniper" | 9.39 s |

All four completed exchanges were saved exactly once. One longer reply showed one estimated playback starvation. Timings exclude speech duration and the approximately 900 ms endpoint pause, and measure writes to the playback pipe rather than acoustic arrival. The two-second goal is unmet. The plant acknowledgement also speculated that it could be a juniper bush; small-model response quality still needs improvement.

Four additional forced-text probes completed, including the longer line that had stalled. Their text streams matched the requested replies. Independent Vosk transcription recovered approximate spoken content but misrecognized names and some words; it is not proof of perfect pronunciation. Owner review of the context-generated audio remains pending.

Live cancellation checks stopped reasoning in 0.0009 s and active playback in 0.064 s, with no cancelled exchanges saved. A subsequent completed reply recovered successfully (brain ready 3.17 s, playback 6.59 s, one estimated gap). These are measured worker-stop times, not acoustic mute measurements.

A reproducible synthetic playback check is available; it creates disposable data before application imports and needs a fresh report directory:

```bash
PYTHONPATH=. .venv/bin/python -B scripts/verify_live_voice_context.py \
  --kit /mnt/data/Companion/sora-liquid-audition \
  --report /tmp/sora-voice-context-check
```

## Automated checks and limitations

```bash
PYTHONPATH=. .venv/bin/python -B -m pytest \
  tests/test_voice_brain.py tests/test_voice_context.py tests/test_fast_local_chat.py \
  tests/test_chat_archive_and_consolidate.py tests/test_chat_range_query.py \
  tests/test_onboarding_persistence.py tests/test_local_single_device_mode.py \
  tests/test_liquid_live.py tests/test_voice_input.py -q
```

Result: 128 passed, 7 skipped, 2 warnings, exit 0. Exact output is in `docs/verification/phase_04_27/tests.txt`. Coverage includes account separation/custom character reload, saved identity, legacy history, deleted accounts, malformed history, concurrent append/archive across three processes, identical retry, provider binding, incomplete streams, cancellation and speech-text mismatch rejection. Legacy pytest wrappers return tuples and emit two warnings; they do not establish that every case in their standalone script passes. Earlier isolated full-script comparison found 81/104 in both baseline and modified code, including 23 existing index-consolidation failures. No claim of full-suite success is made.

The Android build, patch idempotence, Python compilation, shell syntax and dependency consistency were checked. The repository secret scan passed. No app packaging, UI or physical microphone re-test was performed in this phase. The owned phone runner, its lock and ADB forward were removed after checks; the temporary Ollama service was stopped. Verified model caches remain in place. Run commands above start a new session rather than autostarting services.

## Local-data incident and recovery

During an earlier standalone legacy maintenance check in this phase, its index test ignored its intended temporary path and pruned one journal link in the real local memory index. The journal file and its contents were untouched. The link was restored using the existing journal filename. The original link's descriptive wording/layout cannot be verified byte-for-byte. The pruned index and repair note are preserved privately under `/mnt/data/Companion/recovery/phase_04_27/`; user data and these recovery copies are excluded from Git. Subsequent standalone legacy comparisons used disposable data directories. This incident was reported to the owner during the session.

## Handoff

Persona/core-memory/history integration is verified within the terminal prototype's stated bounds. Next proposed phase is 4.28: reduce measured reasoning/prefill and playback delays, investigate starvation, and compare the resulting delivery with the owner's chosen voice sample. Do not report live-conversation readiness or start app integration based on these results alone.

Reference inspected: [Liquid Audio's interleaved generation implementation](https://github.com/Liquid4All/liquid-audio/blob/main/src/liquid_audio/model/lfm2_audio.py). The local runner patch remains a Sora-only customization; no upstream contribution was submitted.
