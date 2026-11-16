# Phase 4.11 — Local Voice Samples

## Samples

The same synthetic assistant reply was saved in a temporary account and passed to the authenticated synthesis route three times. All three clips use the local Piper `en_US-ljspeech-medium` model.

> Hey, it's Sora. I'm glad you're here. We can take it slow today.

| Clip | Audio duration | Synthesis time |
| --- | ---: | ---: |
| `sora-neutral.wav` | 3.96 s | 2.09 s |
| `sora-warm.wav` | 4.71 s | 1.83 s |
| `sora-playful.wav` | 3.76 s | 1.88 s |

The presets change pacing and pauses. Owner listening and preferred delivery are pending. The WAVs are generated artifacts outside the repository, under `sora-voice-samples/` beside the cumulative bundle. No model weights or runtime account data are included in the commit.

## Verification

- Sample generation command: `SORA_SAMPLE_DIR=/home/imam/.codex/visualizations/2026/11/06/01a1b234-e07c-7f00-977d-4d2b2c933bfb/sora-voice-samples SORA_PIPER_MODEL_PATH=/tmp/sora-44-model/en_US-ljspeech-medium.onnx PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B /tmp/sora-411-voice-samples.py`. Exit 0. Each route response was HTTP 200, `audio/wav`, and `no-store`. The three files decoded to 22,050 Hz mono PCM16 with non-silent samples.
- Regression command: `SORA_TEST_PIPER_MODEL_PATH=/tmp/sora-44-model/en_US-ljspeech-medium.onnx PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/sora-44-venv/bin/python -B -m pytest -p no:cacheprovider -q --tb=short tests/test_voice_input.py -k 'synthes or piper'`. Exit 0, 17 passed and 22 deselected.
- To regenerate just the audio using the installed backend and model, run the following from the project root. The output stays in a new temporary directory.

```bash
SORA_PIPER_MODEL_PATH=/absolute/path/to/en_US-ljspeech-medium.onnx \
  PYTHONPATH=. .venv/bin/python -B - <<'PY'
from pathlib import Path
from tempfile import mkdtemp
from voice_output import VOICE_STYLES, synthesize_wav

output = Path(mkdtemp(prefix="sora-voice-samples-"))
text = "Hey, it's Sora. I'm glad you're here. We can take it slow today."
for style in VOICE_STYLES:
    (output / f"sora-{style}.wav").write_bytes(synthesize_wav(text, style=style))
print(output)
PY
```

## Claude Code handoff

This checkpoint changed project records only. Import the cumulative Phase 4.11 bundle into the Sora checkout with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. It requires Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). Record the owner's choice if they provide one. Phase 5 remains deferred to the app stage, and Phase 6 remains paused at 6.1.
