# Phase 4.4 — Local Delivery Styles for Spoken Replies

## Starting checkpoint

- Restored Phase 4.3 (`aa8b8a96f276c728b5acbfb8a3e36e24dffecdec`) by fast-forwarding a fresh temporary Sora checkout with the cumulative bundle. The original project volume and temporary checkout were unavailable.

## Behavior

The authenticated `POST /api/voice/synthesize` route accepts an optional `style` alongside the saved assistant `message_id`. For example, `{"message_id":"reply-id","style":"warm"}`. An omitted style uses Piper's existing settings. The route returns HTTP 400 for unsupported or malformed style values. Audio is generated locally on request and the preset is scoped to that request.

| Style | Pace | Added pause between sentences |
| --- | --- | --- |
| `neutral` | Voice model default | Voice CLI default |
| `warm` | Length scale 1.15 | 0.20 s |
| `playful` | Length scale 0.88 | 0.08 s |

The fixed controls adjust pacing and pauses. Determining when to use a style and choosing an expressive voice model are separate from these presets. [Piper CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md)

## Verification

- Command: `SORA_TEST_PIPER_MODEL_PATH=/tmp/sora-44-model/en_US-ljspeech-medium.onnx PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q -rP tests/test_voice_input.py tests/test_local_single_device_mode.py tests/test_chat_error_copy.py`. Exit 0, 57 passed, 2 skipped.
- Real offline Piper synthesized the same sentence in all three styles. Audio durations were 2.91 s neutral, 3.42 s warm, and 2.72 s playful. Synthesis times were 1.78 s, 1.78 s, and 1.57 s, respectively. The test verifies WAV output and non-silence. Listening and subjective style judgments remain open.
- The opt-in Vosk-only and complete recording-to-reply smoke tests were skipped in this run. Their preceding results are in [Phase 4.3](PHASE_04_03.md). Reuse the Piper setup in [Phase 4.2](PHASE_04_02.md) to rerun synthesis.

## Claude Code handoff

Import the cumulative Phase 4.4 bundle into a clean Sora checkout with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. The bundle includes all local commits since Phase 3.3B. Publish through authenticated access to Emii31/Sora on `origin/main`. Playback controls and testing delivery on the device remain part of later client work.
