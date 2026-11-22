# Phase 4.54 — Benchmark short replies and prioritize phone voice

Ran six synthetic prompts through warmed Qwen 2.5 1.5B and the existing whole-reply Sopro prototype on the laptop. Kept the same voice reference and 250 ms reserve. Each turn used empty disposable chat history and saved one exact exchange. Playback went only to a muted virtual sink.

Playback submission was 3.66–6.68 s after recognized input, with a median of 4.79 s. Five replies stayed within 5–11 words. One was 24 words. Even the shortest missed two seconds. Median chat generation was 2.71 s and median Sopro time to first PCM was 2.06 s. Setup and speech recognition were outside the timing.

Virtual monitor alignment was reliable on five turns and measured 0.01–1.75 s of added delay. The sixth did not match both boundaries closely enough for a continuity conclusion. Whisper recovered the expected words from generated PCM and monitor output on all six turns. That check covers intelligibility of this small sample.

Replayed identical PCM schedules for the two noisiest measured turns with 0.25 and 0.60 s reserves. Both reserves started on the first packet and produced approximately 1.77–1.78 s and 0.91 s of added delay in the two fixtures. The first packet exceeded both thresholds. No buffer or runtime defaults changed.

The owner accepts slower laptop delivery and wants the voice refined and verified on the Motorola. Quality on the phone now determines acceptance. See Phase 4.55 for the on-device build and test.

## Verification

- From `/mnt/data/Companion/recovery/phase_04_54`, ran `PYTHONPATH=/mnt/data/Companion/Miru:/mnt/data/Companion/Miru/scripts /mnt/data/Companion/Miru/.venv/bin/python -B -u short-replies.py real-short`. Exit 0 with six complete replies.
- Ran `PYTHONPATH=/mnt/data/Companion/Miru /mnt/data/Companion/Miru/.venv/bin/python -B -u replay-reserve.py real-short` from the same directory. Exit 0.
- Ran `PYTHONPATH=/mnt/data/Companion/recovery/phase_04_38/whisper-runtime /mnt/data/Companion/sora-nano-audition/venv/bin/python -B check-audio.py real-short` from the same directory. Exit 0.
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_sopro_live.py tests/test_voice_brain.py tests/test_voice_context.py tests/test_voice_playback_diagnostics.py`. Exit 0 with 46 passed. Evidence is under `docs/verification/phase_04_54`.
