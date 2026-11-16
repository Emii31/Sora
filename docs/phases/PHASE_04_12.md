# Phase 4.12 — Expressive Offline Voice Audition

The owner found Piper's pacing presets too flat and asked for a soft, affectionate voice with audible emotional and conversational changes. Auditioned Silencio-2 locally using bundled voices. It supports emotion conditioning and vocal events such as laughter and sighs. NeuTTS-2E is a second candidate with explicit emotions and fixed voices. Only Silencio-2 was installed and run. [Silencio-2 model card](https://huggingface.co/BlueRoseLabs/Silencio-2) [NeuTTS-2E examples](https://github.com/neuphonic/neutts/blob/main/examples/README.md)

## Verification

- Silencio-2 revision `20930f5f6a6bb564f2a8207152fd5c5d8eecff03` was downloaded from its official model repository. CPU-only PyTorch 2.8.0 and the model's requirements were installed in a separate temporary environment. The model weights are CC BY 4.0, derived from Kyutai Pocket TTS, and were kept out of Sora's repository.
- Model and voice inputs were local paths. Inference ran with `HF_HUB_OFFLINE=1` and an audit hook that rejects socket connections and DNS lookups. All four voice auditions and five scene clips decoded as non-silent 24 kHz mono PCM16 WAVs. The generation process peaked at 862 MiB RSS for the five clips, and 1,066 MiB for the process that auditioned four bundled voices.
- Vosk recovered the main words of each scene and both takes of the identical line. It missed the whispered opening and misrecognized the angry greeting. Automated transcription does not establish emotional quality. The neutral and angry WAVs were byte-distinct. The tested weights had SHA-256 `c287646193537d3ca9c1fa536c0edf06b0b14bd0a5f8582caeb460a30f58fdc4`.
- The five scenes used bundled voice `6930`. Render times below exclude the initial voice reference encoding and model load.

| Clip | Conditioning | Audio | CPU render |
| --- | --- | ---: | ---: |
| `playful.wav` | Happy with a laugh cue | 5.76 s | 4.56 s |
| `soft.wav` | Whisper | 4.32 s | 2.64 s |
| `thoughtful.wav` | Sigh cue | 5.04 s | 3.13 s |
| `firm-neutral.wav` | Default delivery | 3.84 s | 2.55 s |
| `firm-angry.wav` | Angry delivery, same line and seed as neutral | 3.76 s | 2.26 s |

The clips are in `sora-expressive-voice/` beside the cumulative bundle. The owner can compare the paired line and choose a voice by ear. Sora's synthesis endpoint still uses Piper. No engine or default speaker was selected for integration.

## Reproduce

Set up the pinned model files in a local directory with its inference code and bundled voices. Run its published requirements in an isolated CPU Python environment. With `PYTHONPATH` pointing at that directory, the following regenerates the comparison using only local files.

```python
from silencio2 import Silencio2TTS

tts = Silencio2TTS.from_pretrained("/absolute/path/to/silencio-model", device="cpu")
line = "Hey. That wasn't okay. I need you to hear me."
tts.save("firm-neutral.wav", line, voice="6930", seed=7)
tts.save("firm-angry.wav", line, voice="6930", emotion="angry", seed=7)
```

## Claude Code handoff

Import the cumulative Phase 4.12 bundle with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD` into a clean checkout starting from Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). Record the owner's feedback before selecting a voice engine. Phase 5 remains deferred to app work, and Phase 6 remains paused at 6.1.
