# Phase 4.13 — Supertonic 3 Voice Audition

The owner described the Silencio-2 clips as broken sounding and requested another provider. This audition uses Supertone's Supertonic 3 model with its official female voices and the CPU ONNX Runtime backend. The test keeps the live Sora synthesis endpoint on Piper pending the owner's selection. [Supertonic 3 model card](https://huggingface.co/Supertone/supertonic-3) [Official Python SDK](https://github.com/supertone-oss-archive/supertonic-py)

## Setup

- Model revision `3cadd1ee6394adea1bd021217a0e650ede09a323`, BigScience OpenRAIL-M, official SDK `supertonic==1.3.1`, ONNX Runtime 1.32.0.
- SDK and model files were kept outside Sora's checkout. The audition used three inference threads, one inter-op thread, 12 synthesis steps, 1.0 speed, English, and seed 7. It disabled automatic downloads and rejected socket calls in Python.
- The five female voices used the same untagged line: “Hey, I'm Sora. Come sit with me for a minute. Tell me what made you smile today.” Three voices also rendered playful and upset lines with the publisher's expression tags.

## Reproduce

With the official SDK installed and the ONNX files and voice styles downloaded to a local folder:

```python
from supertonic import TTS

tts = TTS(model="supertonic-3", model_dir="/absolute/path/to/local-model", auto_download=False,
          intra_op_num_threads=3, inter_op_num_threads=1)
style = tts.get_voice_style("F1")
wav, _ = tts.synthesize("Hey, I'm Sora. Come sit with me for a minute. Tell me what made you smile today.",
                        voice_style=style, lang="en", total_steps=12, speed=1.0)
tts.save_audio(wav, "sora-f1.wav")
```

## Handoff

The clips are in `sora-supertonic-audition/` beside the cumulative bundle. No engine was integrated into the app. Import the bundle from a clean checkout with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. It requires Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). Record the owner's preferred timbre and whether the expressiveness is sufficient before changing the synthesis endpoint.

## Results

- The main offline render exited 0 and produced 11 WAVs. The separate untagged F3 reassurance take brought the total to 12. All generated signals were finite and non-silent at 44.1 kHz mono PCM16. There were zero clipped raw samples in the render reports. Main-process peak RSS was 513 MiB. Individual clips took 4.74–6.92 s to generate, excluding model initialization.
- Vosk recovered the plain and playful dialogue apart from some proper-name errors. It detected the literal word “angry” at the start of all three anger-tagged takes. Exclude those takes from the listening shortlist. The playful takes did not transcribe the tag, which does not establish that the audible delivery will meet the owner's preference.
- Commands: `HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/sora-supertonic-sdk /tmp/sora-44-venv/bin/python -B /tmp/sora-supertonic-audition.py` (repeat with `soft` for the reassurance take). For the plain and tagged takes, verification ran `/tmp/sora-44-venv/bin/python -B /tmp/sora-supertonic-verify.py`. Both exits were 0.
