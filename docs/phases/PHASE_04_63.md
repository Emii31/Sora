# Phase 4.63 — First-sentence delivery on the Motorola

Compared one native Sopro request for the complete reply against the existing Sora sentence scheduler connected to Sopro in a scratch harness. Both modes used the faster Motorola cores, the same approved reference, the same seed, a primed player and a 0.75-second initial buffer. Qwen sent only completed sentence boundaries to speech during generation. The scheduler verified sentence order and full reply coverage before committing the exchange. The test used prerecorded synthetic input and kept the microphone closed.

## Results

| Recording | Whole-reply speaker onset | Sentence-mode speaker onset | Android underruns, whole / sentences |
| --- | ---: | ---: | ---: |
| Tea | 7.13 s | 5.26 s | 0 / 1 |
| Long day | 8.57 s | 7.61 s | 0 / 3 |

The same finalized transcript and reply text reached both modes in each pair. Whisper transcribed every playback word in order when punctuation and case were ignored. On the long-day input, Whisper heard “I have a long day” instead of the fixture's “I had a long day” in both conditions. Each test saved exactly one exchange in disposable history.

Sentence mode issued its first synthesis request 0.61 and 1.61 seconds before full reply finalization, respectively. The wait from completion of the first synthesis request to PCM from the next request was 2.10 and 2.53 seconds. Relative to PCM submission and nominal uninterrupted playback, the largest late chunk arrived 1.12 and 1.78 seconds too late, respectively. Those are transport and buffer estimates. Android separately confirmed playback underruns. Both sentence-mode waveforms differed from their whole-reply controls despite using the same voice reference and seed. Faster onset alone does not establish that they match the approved delivery.

These four measurements cover two matched synthetic pairs. Playback onset is estimated from Android timestamps and the fixture's speech endpoint. Qwen and ASR timing also varied between modes. Keep whole-reply synthesis as the default. The next optimization should reduce the time to prepare a complete reply and preserve one continuous synthesis request. The two-second end-to-end target remains open.

## Verification

- From `/mnt/data/Companion/recovery/phase_04_63`, ran `bash with-awake-phone.sh python3 -B native_phone.py stage` and `source ../phase_04_59/env.sh && bash with-awake-phone.sh /mnt/data/Companion/Miru/.venv/bin/python -B -u sentence_turn.py .75`. Both exited 0. Verified the transferred voice assets and player by hash, then removed the owned Android directory and forwarding. The device stay-awake setting returned to 0.
- From the Sora repository, ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_sentences.py tests/test_voice_sopro_live.py tests/test_voice_brain.py tests/test_voice_context.py tests/test_voice_playback_diagnostics.py`. 64 passed, exit 0. The scheduler tests cover sentence boundaries, cancellation and complete-turn persistence.
- [Structured Motorola comparison](../verification/phase_04_63/motorola-sentence-comparison.json) contains only synthetic transcripts and timing metadata.
