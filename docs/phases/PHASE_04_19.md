# Phase 4.19 — Voice Playback Latency and Emotion Reel

The owner requested live conversation speed with the approved Qwen voice and a longer sample spanning emotions. The original reference and Phase 4.17 model, codec, and sampling remain in use. The standalone audition used the Phase 4.18 Vulkan submission experiment.

## Fast playback of an existing reply

The authenticated local playback route keeps up to eight successful Qwen WAVs in a process-local memory cache. A key includes the authenticated account and its data directory, a digest of the exact reply text, and the current runtime and voice-file identities. Hits are accepted for five minutes. The saved assistant reply must still be present in that account's history. The route serves a cache hit without waiting for the model. The replay optimization uses no files or network and applies to the opted-in resident Qwen configuration. Worker replacement follows runtime and model/reference file changes.

A new text reply still needs synthesis. Earlier audio chunks cannot sustain smooth streaming whenever generation runs slower than playback. Scope this checkpoint to measured replay latency and the audio audition. The cache does not change chat generation, first-time TTS, or live microphone behavior.

## Audition

Each scene was rendered with the same voice reference. The reel uses 0.6 seconds of silence between otherwise unmodified takes. The words and punctuation cue the intended emotions. The Qwen Base model has no independent emotion selector, so delivery should be assessed by listening. The scene labels appear in the listening guide.

## Enable the resident voice

Run these exports before starting the normal Sora process. The voice kit path is the persistent `sora-approved-voice` directory containing the original reference and the `vulkan/qwen-tts-framed` executable.

```bash
export SORA_QWEN_VOICE_DIR=/absolute/path/to/sora-approved-voice
export SORA_QWEN_RESIDENT_DEVICE=Vulkan0
export GGML_VK_MAX_NODES_PER_SUBMIT=256
```

The last setting is the optional GPU scheduling setting measured in Phase 4.18. The replay takes effect automatically when resident Qwen is enabled.

## Verification

- The real Flask endpoint synthesized a 3.68-second saved reply in 23.18 seconds on Intel HD 620, following a 26.41-second warm-up. Seven repeat requests returned byte-identical WAVs from the same account, with a median latency of 1.37 milliseconds. The synthesis lock was held during these replay requests to prove they did not enter the worker. This measures saved-reply playback and excludes chat inference.
- Eleven fresh scenes using the same framed Vulkan runtime took a median of 34.35 seconds each. The median time to the first 80 ms PCM chunk was 3.11 seconds and median synthesis cost was 6.39 seconds per second of audio. With those measured arrival times, uninterrupted streaming would require an initial buffer delay of at least 25.65 to 37.08 seconds, depending on the scene. Fresh reply speech falls short of live conversation speed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -B -m pytest -p no:cacheprovider tests/test_voice_input.py tests/test_local_single_device_mode.py -q` exited 0 with 65 passing and six optional live tests skipped. It covered authenticated replay, account isolation, missing history, reference update invalidation, and worker replacement.
- The 13-scene reel is 86.00 seconds including the pauses. It is mono 24 kHz PCM16, with each source WAV checked for nonzero samples and clipping. The reel's SHA-256 is `e1fc479dc01af51097933304a2228e0e34871877dc106c2e42347657887f5277`. It is stored outside Git with its listening guide, individual WAVs, reproduction scripts, and test logs in `sora-voice-latency/phase-4.19/`.
