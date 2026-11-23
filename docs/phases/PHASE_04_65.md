# Phase 4.65 — Opt-in four-thread Ollama voice profile

The terminal voice command now accepts `--ollama-threads 4`. Add it to the existing launch command when its chat tier points directly to a local Ollama server, for example `http://127.0.0.1:11434/v1`. The option switches voice chat and its warmup to Ollama's native `/api/chat` on the configured loopback host and port. It passes the requested thread count along with the configured model and existing generation budget. Omitting the flag retains the OpenAI-compatible voice route. Web chat and provider settings are unaffected.

The voice brain keeps the same checks for bounded, complete replies and cancellation. Normal speaker delivery uses one Sopro request per reply. The Android benchmark uses the existing scratch player and faster-core profile. It uses disposable data and prerecorded speech.

## Six-turn Motorola session

Every turn used the production voice brain and four-thread option, local Whisper, the same Sora account context, and whole-reply Sopro synthesis. The player used the 0.75-second initial buffer. The six turns ran in one session, preserving every preceding exchange. Sora recalled the stated favorite color, blue, after an intervening turn about tea. The session ended with exactly 12 history messages.

| Turn | Chat dispatch to completed reply | End of speech to speaker | Underruns |
| --- | ---: | ---: | ---: |
| State favorite color | 1.79 s | 5.97 s | 0 |
| Tea | 1.53 s | 5.78 s | 0 |
| Recall favorite color | 1.57 s | 5.69 s | 0 |
| Long day | 3.42 s | 7.59 s | 0 |
| Quiet | 3.84 s | 8.16 s | 0 |
| Cookie | 4.35 s | 8.83 s | 0 |
| Median | 2.61 s | 6.78 s | 0 |

All six replies drained through the built-in speaker. The first test sequence used a synthetic cat name that Whisper misheard. It finished playback but failed the memory fixture's assertion. The second sequence used a prechecked favorite-color statement and question. Whisper still transcribed the long-day fixture as “I have a long day,” consistent with earlier tests. The final evidence covers recent history recall, one scripted session and no microphone. The first and later turns had different prompts, saved history and reply lengths, so the timing increase does not isolate any one of those factors. No automatic-thread baseline was replayed in this phase.

## Verification and handoff

- From `/mnt/data/Companion/recovery/phase_04_65`, ran `bash with-awake-phone.sh python3 -B native_phone.py stage` and `source ../phase_04_59/env.sh && bash with-awake-phone.sh /mnt/data/Companion/Miru/.venv/bin/python -B -u sustained.py`. The final runs exited 0. Removed the owned Android files and forwarding and checked that the stay-awake value returned to 0.
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_brain.py tests/test_voice_context.py tests/test_voice_sopro_live.py tests/test_voice_sentences.py tests/test_voice_continuous.py tests/test_voice_input.py tests/test_voice_playback_diagnostics.py`. 125 passed and six skipped, exit 0.
- Checked that the terminal help lists the flag and that `--ollama-threads 0` exits with an argument error before starting the session. Unit tests cover the local native request, one-token warmup, ordered sentence callbacks, rejection of relays and incomplete streams, and existing default-provider behavior.
- [Six-turn Motorola replay](../verification/phase_04_65/motorola-six-turns.json) contains only synthetic text, timing and output metadata.

Keep this profile opt-in. The two-second live target remains open. Next, isolate how much of the later-turn delay comes from processing recent history and see whether response preparation can be shortened while preserving recall.
