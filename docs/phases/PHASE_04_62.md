# Phase 4.62 — Motorola playback continuity and full-turn replay

Tested an Android player that puts PCM in the AAudio output buffer before starting and writes to ADB from a separate thread. Both changes were confined to the benchmark. Sopro used the approved reference, seed and synthesis settings.

## Fixed-text playback

Both fixed lines produced identical complete PCM across all three settings. All six playbacks drained every frame to the phone speaker. The faster-core profile was verified before each request.

| Playback setting | Reply onset / underruns | Playful onset / underruns |
| --- | ---: | ---: |
| Previous player, 0.25 s buffer | 2.11 s / 0 | 2.85 s / 0 |
| Primed player, 0.25 s buffer | 2.01 s / 3 | 2.67 s / 0 |
| Primed player, 0.75 s buffer | 3.13 s / 0 | 2.84 s / 0 |

The reply initially delivered less than 0.75 seconds of PCM, so the larger buffer waited for a second chunk. The playful line's first chunk already met the threshold. First-PCM and inter-chunk timings varied. The test does not isolate the effect of priming from the separate writer or each request's synthesis rate. Use the 0.75 s setting as a continuity candidate.

## Full conversation replay

Ran two synthetic recordings of the same sentence through the energy endpoint, local Whisper, local Qwen and Sopro, with playback through the Motorola speaker. The endpoint remained at 1.2 seconds. Alternated the CPU mode order across the recordings. Both modes used the new player and the 0.75-second buffer. All four turns recognized the exact sentence, delivered the same reply and saved one exchange each in disposable history. All four complete PCM hashes matched Phase 4.59 and every frame drained.

| Recording | All-core onset | Faster-core onset | Underruns |
| --- | ---: | ---: | ---: |
| Tea sentence, voice one | 7.12 s | 6.77 s | 0 in both |
| Tea sentence, voice two | 6.68 s | 6.21 s | 0 in both |
| Median | 6.90 s | 6.49 s | 0 in all four |

Onset is estimated from the end of fixture speech and the Android playback timestamp. The USB clock estimate had a 30 ms half round trip. The two all-core and two faster-core turns are a small sample drawn from one sentence. Recognition and Qwen times varied across turns, so the 0.41 s median whole-turn gain cannot all be attributed to phone CPU scheduling. No microphone was opened.

## Verification and handoff

- Built the scratch Android player with the existing NDK's `aarch64-linux-android28-clang -Wall -Wextra -Werror -O2 phone-player.c -laaudio -o phone-player`, exit 0.
- From `/mnt/data/Companion/recovery/phase_04_62`, ran `bash with-awake-phone.sh python3 -B native_phone.py stage`, `bash with-awake-phone.sh python3 -B continuity.py`, and `source ../phase_04_59/env.sh && bash with-awake-phone.sh /mnt/data/Companion/Miru/.venv/bin/python -B -u whole_turn.py .75`. The runs exited 0. Removed only the owned temporary directory and forwarding. Android's original stay-awake setting was restored to 0.
- From the Sora repository, ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_sopro_live.py tests/test_voice_playback_diagnostics.py tests/test_voice_input.py tests/test_voice_brain.py tests/test_voice_context.py`. 86 passed, 6 skipped, exit 0.
- [Fixed-text measurements](../verification/phase_04_62/fixed-text-playback.json) and [whole-turn measurements](../verification/phase_04_62/whole-turn-replay.json) contain only synthetic recordings' text and timing metadata.

Keep the faster-core player and 0.75-second buffer experimental. The two-second end-to-end target remains open. On the faster-core turns, recognition and finalized text together already took 3.17–3.65 seconds, so the next iteration should target earlier safe delivery of a complete sentence while preserving playback continuity and evaluating the approved voice on varied replies.
