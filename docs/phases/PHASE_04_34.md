# Phase 4.34 — Expressive KittenTTS 2 audition

Started from `e48d244`. The owner rejected Piper Amy Low's delivery. The audition used the second-generation KittenTTS model, bundled female voice Kiki, its released student_w4 decoder, and the published C++ CPU wheel 0.2.0 with PyTorch 2.13.0+cpu. The runtime used its Expressive preset, seed 1234, and four threads on the i5-7300U. The model files and config match the official revision `c93cb7c271baa51d9ae8204d5277988906f235a2`. [CPU runtime](https://github.com/KittenML/kitten-tts-2-cpp) [Expression controls](https://github.com/KittenML/KittenTTS/blob/main/docs/voices-and-expression.md) [Model license](https://huggingface.co/KittenML/kitten-tts-2/blob/c93cb7c271baa51d9ae8204d5277988906f235a2/LICENSE.md)

Tender and stern takes use the same line, speaker, preset and seed. The leading direction is the only text difference. The local Vosk check returned the full expected wording for each. The takes use native 24 kHz audio. The comparison inserts a 0.65-second pause and exports PCM16. Subjective delivery is for the owner to assess.

| Take | Speech duration | Warm generation wall time |
| --- | ---: | ---: |
| Tender | 4.00 s | 101.29 s |
| Stern | 3.80 s | 99.28 s |
| Playful | 6.12 s | 131.84 s |

Model initialization took 6.24 seconds after import. The measured synthesis took 21.5–26.1 seconds per second of audio. It fails the live voice requirement on this laptop before speech recognition or chat inference. The six-minute run limit left five planned takes and the streaming probe unfinished. The phone and in-app pipeline are untested.

The 15.22-second reel plays tender, stern, then playful. It is saved at `/mnt/data/Companion/recovery/phase_04_34/kiki/kiki-tender-stern-playful.wav`. The playful take includes an inline laugh cue. The local transcript caught a syllable at that position while retaining the intended spoken words. [Verification](../verification/phase_04_34/RESULTS.md) The isolated assets, environment and audition script are stored alongside it for the handoff. Repeat with the same cached release using:

```bash
cd /mnt/data/Companion/recovery/phase_04_34
HF_HUB_OFFLINE=1 venv/bin/python audition.py --assets model --output kiki-repeat
```

For the next trial, prioritize an expressive engine with a smaller CPU inference path and measure a short first-audio probe before committing to a long reel. EmotiVoice has documented emotion prompts, and MOSS-TTS-Nano has a released CPU ONNX pipeline with reference-based delivery. Neither has been timed on this laptop. [EmotiVoice](https://github.com/netease-youdao/EmotiVoice) [MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano)
