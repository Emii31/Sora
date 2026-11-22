# Phase 4.50 — Motorola microphone test

The owner requested a test using the Motorola Moto G Stylus 5G (2024) microphone because the laptop microphone had problems. Used the checksum-verified portable scrcpy 5.0.1 runtime over USB with video, control and phone-audio playback disabled. Model inference and response playback stayed on the laptop. The test used disposable Sora data.

The live USB route was tried twice. The private PipeWire source carried a synthetic check tone. The scrcpy stream initially landed on a different sink and the subsequent attempted stream move could not be verified. Both runs were stopped before prompting the owner to speak. A recording-and-replay fallback then captured phone speech in a disposable WAV. An initial silence filter removed the audio. The successful run used the raw mic capture, resampled to 16 kHz mono PCM16 without silence trimming or gain changes.

The local recognizer recovered the intended sentence on one repetition and included a near match from another repetition. The existing Sora CLI generated a new reply via Ollama and played it through the laptop's normal speaker sink using native Sopro. The test verified one exchange in disposable storage. Playback began 5.91 seconds after recognition, with two estimated playback gaps. That measurement excludes the recording window, model warmup, and transcription. No live streaming or microphone-to-speaker latency was verified, and acoustic playback on the final trial was not independently recorded.

Test harness and timing metadata are in `/mnt/data/Companion/recovery/phase_04_50`. Run `/mnt/data/Companion/Miru/.venv/bin/python -B -u record-and-replay.py` from that directory and wait for the explicit capture cue. The current harness needs a fresh report location for every repetition. The microphone, USB forwarding and temporary PipeWire devices were closed. The recording and temporary account were removed. No app configuration was changed.

[scrcpy microphone forwarding documentation](https://github.com/Genymobile/scrcpy/blob/master/doc/audio.md)
