# Phase 4.49 — Native Sopro in the local voice loop

The owner authorized an opt-in conversation test with native Sopro. The terminal voice prototype now accepts an explicit Sopro runtime, local model and reference WAV. The prototype warms the fixed voice from the approved Liquid reassurance take. It reuses the existing local recognition, account-scoped chat and PipeWire playback. The normal Liquid launch path and app voice configuration retain their defaults.

The local Sopro worker accepts only complete text replies and runs on loopback. It streams PCM in bounded chunks, stops the turn on an incomplete response, and makes a completed reply eligible for history only after playback completes. The 0.25-second starter buffer is experimental. Speaker continuity is measured by estimates from the playback pipe, which does not capture actual speaker output.

## Measured turns

All three tests used disposable Sora data and the installed local Ollama Qwen2.5 1.5B Instruct model. No human microphone audio, conversation text, or runtime credentials were saved in the repository. Each completed turn saved one exchange in its temporary directory before that directory was removed.

| Test | Chat ready after recognition | First playback write after recognition | Estimated playback gaps |
| --- | ---: | ---: | ---: |
| Prerecorded synthetic input, virtual PipeWire sink | 3.94 s | 8.62 s | 4 |
| Physical microphone, default speaker sink | 2.59 s | 4.34 s | 2 |
| Microphone retry, explicit cue and higher capture threshold | 2.64 s | 4.28 s | 2 |

The owner confirmed hearing the first reply. The retry used a pre-listen Enter gate and a higher RMS threshold. Both microphone transcriptions differed from the intended test sentence, and both captures reached the utterance limit before the expected pause. The implementation now records a speech-end timestamp only when a pause ends capture. The reported playback times begin after recognition. Microphone-to-audible-speaker latency remains unverified. The prerecorded test verified a recognized prompt with a relevant live-generated reply. These checks do not establish live-chat readiness.

## Reproduce

The benchmark launcher is `/mnt/data/Companion/recovery/phase_04_49/verify-turn.py`. The prerecorded run starts an isolated Ollama instance, invokes the normal CLI with the Sopro flags and uses a temporary virtual sink. Its `--live` option uses the default microphone and speaker for one interactive turn. Run with `--live --retry` to test the gated microphone start. All modes stop their workers after the test. Use fresh report directories for reruns. [Timing evidence](../verification/phase_04_49/timings.json)

The runtime binary and model are the previously verified Phase 4.48 and 4.47 artifacts, respectively. The approved Liquid recording is retained. The next test should isolate microphone endpointing and the combined chat/speech slowdown before any use as a default.
