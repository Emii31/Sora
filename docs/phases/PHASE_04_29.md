# Phase 4.29 — Experimental Sentence Streaming and Turn Reset

## Outcome

Backend experiment completed on 2026-11-20 from `8e0a018a6d6b3245d0963f7170ba83e810b936ff`. Sentence-mode overlap, persistence boundaries, cancellation and recovery are verified as described below. **The feature remains experimental and off by default. Delivery quality is not approved for everyday use.** Earlier starts came with longer output and possible repeated speech. Consistent two-second live conversation is still unachieved.

## Implementation

- `voice_sentences.py` conservatively releases punctuation-delimited text with lookahead, holding common abbreviations, initials, decimals, ellipses and the final tail. It preserves the original text. The final tail is released only after a valid provider completion; earlier sentences can already have been heard if a later provider error occurs.
- `LocalVoiceBrain.reply(..., on_sentence=...)` publishes completed text boundaries while reading the existing loopback provider stream. Warmup and whole-reply calls retain their earlier behavior. `LocalVoiceContext` keeps this work in the selected account scope.
- `VoiceTurn` uses a four-item queue and one speech worker, retaining a single playback process across sentence requests. It limits the total reply to 16 segments and 30 seconds of PCM. User interruption stops both workers. A speech failure aborts the brain connection without disguising the error as a user cancellation. No exchange is saved until the brain, all speech requests and playback complete successfully.
- Sentence speech requests use the same selected Liquid model and interleaved mode, but each sentence has a fresh synthesis context. They currently include an explicit reading instruction. This **changes generated audio/cadence**, even when words match. Matching text-stream output does not establish matching audible words or quality.
- A native reset fix restores TEXT modality and clears outstanding PCM at each new turn. Previously an interrupted audio turn could leave the next request beginning in audio mode despite clearing the language-model context. The private runner patch now includes `tools/mtmd/mtmd.cpp`; the launcher requires health capability `turn_reset: 1` as well as forced speech support. No dependency upstream contribution was made.
- Plain transcripts remain limited to 2,000 characters. Forced-speech context has bounded 2,048-character headroom for the reading instruction; spoken reply text retains its 2,000-byte bound. No text is silently truncated.

The default whole-reply path is retained. `--sentence-streaming` is explicitly experimental and mutually exclusive with `--smooth-long-replies`. Fixed buffer overrides continue to work. App UI, wake-word activation, native phone capture and acoustic echo cancellation remain outside this phase.

## Run and reproduce

The current local kit source has been updated and rebuilt. Rebuild the pinned private runner before using this revision; the health check rejects an older binary:

```bash
cd /mnt/data/Companion/Miru
bash scripts/build_liquid_voice_runner.sh /mnt/data/Companion/sora-liquid-audition
```

With the existing local Ollama service and installed Qwen model running, and the Motorola authorized over USB:

```bash
PYTHONPATH=. .venv/bin/python -B scripts/live_liquid_voice.py \
  --kit /mnt/data/Companion/sora-liquid-audition \
  --vosk-model /home/imam/Projects/openwakeword-train/model/en/vosk-model-small-en-us-0.15 \
  --sentence-streaming
```

Omit the final option for the existing default. Enter interrupts; `q` + Enter exits. Completed history still uses the existing account store. A failed later segment can leave a partial answer heard aloud, but no partial exchange is saved.

Disposable verification and controlled comparison (fresh report directories required):

```bash
PYTHONPATH=. .venv/bin/python -B scripts/verify_live_voice_context.py \
  --sentence-streaming --kit /mnt/data/Companion/sora-liquid-audition --report /tmp/sora-memory-429
PYTHONPATH=. .venv/bin/python -B scripts/benchmark_voice_sentences.py \
  --save-audio --kit /mnt/data/Companion/sora-liquid-audition --report /tmp/sora-sentences-429
```

The comparison uses two alternating-order pairs of the same fixed three-sentence fixture. Both modes get the exact prompt prefilled outside timing, fresh empty history and a fixed 0.5-second playback reserve. Pairs with differing generated text are excluded from the playback-saving calculation. This is a small controlled experiment, not a natural-conversation benchmark.

## Final real-device results

Both final pairs produced the same requested text in both modes:

| Pair | Whole reply playback | Sentence playback | Whole reply finished | Sentence reply finished |
| --- | ---: | ---: | ---: | ---: |
| 0 | 4.92 s | 2.09 s | 15.31 s | 24.42 s |
| 1 | 5.33 s | 3.31 s | 15.94 s | 25.61 s |

In both sentence cases, playback began before the brain finished (3.08 s and 4.05 s). Starts saved 2.83 s and 2.02 s in these fixtures, **but completion became substantially slower**. Generated sentence audio was 16.82 s versus 7.98 s for whole mode. Estimated playback gaps remained (4/7 in sentence mode, 3/3 in whole mode). Pipe-write estimates are not acoustic measurements. Automatic recognition flagged a possible repeated "take a slow breath" in the sentence clip; listening confirmation is pending. This tradeoff blocks enabling sentence mode by default.

Timings begin after recognized input, with warm prompt conditions. They exclude startup, speech duration, recognition and the approximately 900 ms endpoint pause. The best 2.09-second result is not evidence of two-second end-of-speech live conversation.

Four final memory checks passed Sora identity, saved jasmine-tea preference, new Juniper acknowledgement and restart recall. Playback starts were 3.50/3.49/3.44/6.26 s, with estimated gaps still present. These synthetic recognized-input checks used real local Qwen, phone Liquid inference, laptop playback and saved history. No new human microphone test occurred, and model-generated flourishes were not independently fact-checked.

Actual cancellation during reasoning stopped both workers in 0.041 s; cancellation during playback took 0.092 s. Neither saved messages. A subsequent turn completed and saved exactly one exchange. These measure worker shutdown, not physical acoustic mute timing.

## Failure investigation and limits

The first memory run failed on the short forced line "Juniper is a great name for a plant, Alex!": generic speaker context produced more than the 30-second audio limit. Isolated probes confirmed that failure was not specific to the Python sentence queue. A reading-context test immediately after an aborted turn also failed; source inspection then found the stale modality reset path. A fresh explicit-reading probe completed the same line in 5.98 s with 3.66 s of audio. The native reset was corrected and final memory/cancellation checks passed.

However, the final reading-conditioned comparison had much longer speech and a recognition-flagged repetition. A separate fresh probe using the actual conversational input completed the problematic line in 5.90 s with 3.74 s of audio. That is a lead for further work, not a deployed or broadly verified fix. Source-model speech generation can still fail or produce imperfect audio despite a matching text stream. Current protective limits stop failures; they do not prove speech fidelity.

Canonical JSON evidence and test output are in `docs/verification/phase_04_29/`. Earlier attempts, logs and synthetic comparison WAVs are retained privately under `/mnt/data/Companion/recovery/phase_04_29/`. The final WAVs are in `comparison-final/`; they concatenate generated PCM and do not include extra wall-time starvation pauses. No raw human recording, real memory, credentials or recovery dumps are published.

## Automated and native checks

```bash
PYTHONPATH=. .venv/bin/python -B -m pytest \
  tests/test_voice_sentences.py tests/test_voice_brain.py tests/test_voice_context.py \
  tests/test_fast_local_chat.py tests/test_chat_archive_and_consolidate.py \
  tests/test_chat_range_query.py tests/test_onboarding_persistence.py \
  tests/test_local_single_device_mode.py tests/test_liquid_live.py tests/test_voice_input.py -q
```

Result: **168 passed, 7 skipped, 2 existing legacy return-value warnings**, exit 0. Coverage includes arbitrary text chunk boundaries, early callbacks, provider truncation, consumer errors, mismatch, cancellation under queue backpressure, audio/segment limits, no partial-history saves, and mutual exclusion of playback modes. Earlier standalone legacy-suite limitations remain as recorded in Phase 4.27; no full-suite success is claimed.

Python compilation and CLI help passed. Android rebuild used the existing CMake/NDK target, exit 0. The updated patch applied to a clean copy of the pinned source and reproduced all four built source files exactly; reverse-check passed on the local kit. All implementation and experiments were local through Codex, without remote dependency-repository changes.

## Next action

Keep whole-reply mode as the default. Proposed Phase 4.30: investigate continuous speech-model context and conversational conditioning to reduce sentence resets, repetition and total completion delay, then seek owner listening review. Recognition accuracy and end-to-end latency still need their own checks. Do not promote this experimental mode based on first-playback timings alone.
