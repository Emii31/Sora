# Phase 4.53 — Compare Sopro sentence streaming

Recorded token arrivals from three real, warmed Qwen 2.5 1.5B replies to synthetic prompts. Replayed the exact same token text and timing for each pair, with the same local Sopro runtime, 250 ms playback reserve, and Liquid reassurance reference used for the Phase 4.51 phone trial. The two longer fixtures ran in opposite mode orders. Each turn started with empty disposable history and saved one exact exchange. The sentence variant used the existing sentence worker in a scratch harness, with one Sopro request per sentence.

## Results

| Fixture | Seconds to start, whole / split | Seconds to finish, whole / split | Added playback delay, whole / split |
| --- | ---: | ---: | ---: |
| Reassurance, three sentences | 4.66 / 2.69 | 11.25 / 10.06 | 0.75 / 3.38 |
| Playful, two sentences | 4.66 / 3.66 | 8.85 / 8.72 | 0.23 / 1.97 |
| One-sentence control | 3.16 / 2.66 | 4.43 / 4.05 | 0.07 / 0.15 |

Splitting started the longer replies 1.00–1.96 seconds earlier. Playback preceded the final chat token in the reassurance case only. The one-sentence control made one identical-text speech request in either mode and started about 0.50 seconds apart. Treat individual timing differences as subject to runtime variation.

The virtual monitor aligned reliably with generated PCM for all six turns. Separate sentence requests increased added playback delay by 1.74–2.63 seconds on the longer replies. The largest single added gap was 1.62 seconds in the split reassurance reply. This excludes pauses already present in the synthesized PCM. Whisper tiny.en recovered all 29 expected words per mode after punctuation normalization. This word check does not evaluate naturalness or emotional delivery.

These are laptop timings from the start of processing recognized text to playback submission and turn completion. The isolated Ollama server was stopped before token replay, so the measurements exclude CPU contention between Qwen and Sopro. The test used a muted virtual sink and did not open a microphone, play through speakers, or measure real conversational response time.

Keep Sopro’s existing whole-reply path. The earlier start in this experiment came with long gaps. For the next performance test, compare complete short replies on the real local model using warmed synthesis and inspect both time to first sound and continuity before using the phone again.

## Verification

- Ran `PYTHONPATH=/mnt/data/Companion/Miru:/mnt/data/Companion/Miru/scripts /mnt/data/Companion/Miru/.venv/bin/python -B -u compare-sopro.py matched-2` from `/mnt/data/Companion/recovery/phase_04_53`. All six turns completed and the command exited 0. An initial attempt had required the playful model answer to have exactly three sentences. The final run retained a genuine two-sentence reply and verified exact text across the pair.
- Ran `PYTHONPATH=/mnt/data/Companion/recovery/phase_04_38/whisper-runtime /mnt/data/Companion/sora-nano-audition/venv/bin/python -B check-words.py matched-2` from the same directory. Exit 0.
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_sentences.py tests/test_voice_sopro_live.py tests/test_voice_playback_diagnostics.py`. Exit 0 with 29 passed. Verified benchmark processes and temporary audio devices were removed.
- The two scripts, captures, generated clips, and token traces remain in the recovery directory. Results and word checks are in `docs/verification/phase_04_53`. No runtime code was changed.
