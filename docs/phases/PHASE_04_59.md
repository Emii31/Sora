# Phase 4.59 — Transcript-gated reply preparation

Tested whether starting the local Qwen turn during the existing 1,200 ms listening pause can lower the Motorola reply delay. The scratch prototype starts one draft after 400 ms of silence and requires an exact match of the final transcript, account, data directory, character and full conversation input before reusing it. Resumed speech cancels the draft. Changed context, changed text, an empty draft or a draft error uses ordinary final inference. Synthesis and history persistence wait for final validation.

## Measurements

| Synthetic replay to Motorola speaker | Ordinary | Early draft |
| --- | ---: | ---: |
| End of speech to finalized reply text | 3.58 s | 2.96 s |
| End of speech to first PCM submitted | 5.61 s | 5.79 s |
| End of speech to estimated speaker onset | 5.79 s | 5.86 s |
| Android underruns | 0 | 0 |

The speaker timestamps use AAudio and a USB clock estimate. These runs used the same synthetic input, recognized text, generated reply, native Sopro settings, approved reference and seed. Both saved exactly one exchange in disposable storage and produced identical PCM with SHA-256 `26fd81d11068581212e02a386d1a176222635bb2d2e2892ef1b69e9c78035ac8`. The phone microphone stayed closed.

Two additional pairs reused warm models and alternated the mode order. They measured time to first generated PCM without playing it. Ordinary to draft went from 4.96 to 5.30 seconds in the first pair and 5.01 to 4.83 seconds in the second. All four audio hashes matched the speaker replay. The synthetic hesitation test discarded the draft when speech resumed. The usual-temperature reply-preparation replay sometimes produced different wording, which limits timing comparisons across those runs.

## Verification and handoff

- Scratch prototype tests ran with `.venv/bin/python -B -m pytest -q test_early_reply.py` in the prototype environment. Seven passed.
- Project regression command `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_liquid_live.py tests/test_voice_input.py tests/test_voice_brain.py tests/test_voice_context.py tests/test_voice_sopro_live.py tests/test_voice_playback_diagnostics.py` returned 126 passed and six skipped.
- The test device cleanup removed the temporary session. ADB listed no forwarded ports and the prior Android stay-awake setting was restored to 0.
- Replay results are in [reply-preparation.json](../verification/phase_04_59/reply-preparation.json) and [motorola-replay.json](../verification/phase_04_59/motorola-replay.json). Prototype scripts are under `/mnt/data/Companion/recovery/phase_04_59`.

Keep the prototype outside the default voice path. The experiment found no repeatable improvement in playback onset and leaves the two-second live target open. The next step is to profile native Sopro startup by stage with fixed reply text and the approved voice, then repeat the speaker measurement on any candidate that produces identical audio.
