# Phase 4.15 — Natural Dialogue with Qwen3-TTS VoiceDesign

The owner's seven-emotion NeuTTS-2E sample fell short of the spontaneous delivery they want. Sophie is no longer selected for integration. This test auditions Qwen3-TTS VoiceDesign 1.7B with a natural-language acting direction for one continuous turn. [Qwen VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)

## Setup

- C++ runtime `ServeurpersoCom/qwentts.cpp` at `f1a6924789883bd92eeb59176793a94af55730b3`, with GGML submodule `0d403add5cb6329935290f02462e1072045aacd2`. Build only the `qwen-tts` command for the local CPU. [CPU runtime](https://github.com/ServeurpersoCom/qwentts.cpp)
- Q4_K_M talker and matching audio tokenizer from `Serveurperso/Qwen3-TTS-GGUF`, pinned at `b7ee2e8c7459c3bea99da23e3d178125a7d1713c`. Both assets are verified against their published SHA-256. The combined download is 1.44 GB. [Quantized assets](https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF)
- Read the spoken dialogue on stdin and supply the acting direction through `--instruct`. The sample asks for conversational English from a young adult woman, moving from worry through a pause into relief. The standalone runtime uses local weights. Sora's live provider remains Piper.

## Reproduce

After building the CPU runtime and obtaining the two matching model files, run:

```bash
printf '%s\n' "Hey... you're home. I was starting to worry. Come here a second. I missed you." |
  qwen-tts --model qwen-talker-1.7b-voicedesign-Q4_K_M.gguf \
    --codec qwen-tokenizer-12hz-Q4_K_M.gguf --device CPU --lang English \
    --seed 7 --max-new 180 \
    --instruct "A young adult woman, warm natural American English, close and conversational. It's a private conversation. Start quietly with genuine worry, hesitate briefly, then let the tension fall away. End with an audible smile, tender and relieved. Use natural pauses and breaths, like spontaneous conversation." \
    -o sora-worry-to-relief.wav
```

The model generates a new voice from a description. This test does not establish a stable speaker identity across independent generations. No private conversation or reference recording is used.

## Verification

- The CPU-only build succeeded using CMake 3.22.1 with `GGML_NATIVE=ON` and BLAS disabled. The model download resumed from saved ranges and both published SHA-256 digests matched.
- Generated `sora-worry-to-relief.wav` offline, with one synthesis request for the whole line. The 7.12-second, 24 kHz mono PCM16 result took 56.16 seconds wall time on the i5-7300U. The runtime reported 46.12 seconds for generation and decoding, excluding startup. Its peak RSS was 3,126 MiB. No clipping was recorded in the PCM output.
- The local Vosk check recovered the whole script, normalizing “you're” to “your.” The output checks confirm the words and usable WAV encoding. Voice quality, acting, and same-character performance across a broader range of emotions remain for the owner's review. No model was built into Sora.
- Commands: `python3 -B /tmp/sora-qwen-probe/voice.py` and `/tmp/sora-neutts-venv/bin/python -B /tmp/sora-qwen-probe/verify.py` both exited 0.

## Handoff

Import the cumulative Phase 4.15 bundle with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD` into a clean checkout at Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). The audition WAV and model files are outside Git. Review the clip before choosing whether to pursue this engine. Application work remains deferred.

## Final voice reference

On 2026-11-17, the owner selected this exact take as Sora's final voice. The reference remains at `sora-qwen-audition/sora-worry-to-relief.wav` beside the cumulative bundle with SHA-256 `5ad5d7d8073ad5fb19c0abbf33373203600612f95d30e8432a53de0cb062946c`. Its spoken transcript is the input in the reproduction command above. Use the waveform as the reference when testing speaker consistency across replies. The app still uses Piper pending integration, and the measured 56.16 s cold render remains the local latency baseline.
