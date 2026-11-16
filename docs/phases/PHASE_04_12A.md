# Phase 4.12A — Female Voice Audition

The owner asked to hear several female voices. The previous main audition used Silencio-2 speaker `6930`, which the LibriSpeech metadata labels male. This audition uses the bundled `2094` and `3575`, both labeled female, plus Alba MacKenna's published casual reference. [BlueRose Labs speaker IDs](https://huggingface.co/BlueRoseLabs/Silencio) [LibriSpeech speaker metadata](https://huggingface.co/datasets/s3prl/librispeech_metadata/blob/main/SPEAKERS.TXT) [Kyutai voice source and terms](https://huggingface.co/kyutai/tts-voices#alba-mackenna)

All three voices use Silencio-2 at revision `20930f5f6a6bb564f2a8207152fd5c5d8eecff03` and seed 7. Alba's voice reference is `alba-mackenna/casual.wav` from Kyutai revision `323332d33f997de8394f24a193e1a76df720e01a`, published under CC BY 4.0. Only the generated dialogue is in the audition clips.

Each reel contains the same four scenes, in order. The pauses between scenes are 0.55 s.

| Scene | Conditioning | Line |
| --- | --- | --- |
| Soft | Whisper | Hey. Take a breath. We can go slow. |
| Playful | Happy and a laugh cue | You did that just to make me laugh, didn't you? It worked. |
| Thoughtful | Sigh cue | Hmm. I think I know what I want to say now. |
| Upset | Angry | Hey. I'm upset about what happened. Can we talk about it? |

## Reproduce

In the separate CPU Python environment from [Phase 4.12](PHASE_04_12.md), use `Silencio2TTS.from_pretrained(<local-directory>, device="cpu")`. Use each speaker ID or the local Alba file for `voice`. Render the lines with `seed=7`, `emotion="whisper"`, `emotion="happy"`, `emotion=None`, and `emotion="angry"` respectively. Insert `[laugh]` before “It worked” and `[sigh]` before “Hmm”.

## Handoff

The generated tracks are in `sora-female-voices/` beside the cumulative bundle. The bundle contains the audition record and no voices or weights. Import it into a clean Sora checkout with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD`. It requires Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). Sora still uses Piper. Record the owner's preferred voice before integration.

## Verification

- Generation command: `HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/sora-silencio-model /tmp/sora-silencio-venv/bin/python -B /tmp/sora-female-audition.py`. Exit 0. The Python audit hook refused any socket activity, and all 12 takes were finite and non-silent.
- `ffprobe` verified 24 kHz mono PCM16 across the three reels. A (`2094`) lasts 19.97 s, B (`3575`) 16.13 s, and C (Alba) 17.73 s. Warm CPU generation took 2.08–3.36 s per scene. The separate first-use reference encoding took 1.49–5.48 s per voice. Peak process RSS was 1,067 MiB.
- No application code changed. Owner listening is the remaining check.
