# Phase 4.51 — Live Motorola microphone test

The existing Linux terminal prototype received live Motorola microphone audio via USB. A scratch scrcpy wrapper wrote raw stereo audio in a WAV stream to a temporary FIFO. FFmpeg converted it to 16 kHz mono PCM16. The final run fed that stream directly to the recognizer through a test-local `pw-record` shim. Qwen and native Sopro ran locally on the laptop. This was a disposable test with no production configuration changes.

- The synthetic transport probe received 22,400 PCM bytes for 0.70 seconds of audio. The synthetic companion turn through a temporary sound device recognized part of its sentence and returned a reply.
- The owner confirmed speaking on the first live attempt. Recognition timed out with no complete utterance when routed through the temporary sound device.
- The direct retry used a lower speech threshold and bypassed that device. The recognizer returned “I had a long” from the requested “I had a long day.” Sora replied “I'm here, ready to chat!” and the harness verified one exchange in disposable storage. Both input routing and the threshold differed between the two runs.
- The final turn started playback submission 5.93 seconds after estimated speech end and 3.82 seconds after recognition. The pipeline reported one estimated playback gap. These timings exclude model warmup and do not measure acoustic speaker output. They establish one live turn with a partial transcript. Conversational speed and reliable sentence recognition remain open.

The scratch helper `phone-pcm.py`, wrapper `live-usb-turn.py`, and metric-only `direct-report-2/turn/turns.jsonl` are under `/mnt/data/Companion/recovery/phase_04_51`. The run exited successfully and removed the disposable account, temporary audio devices and USB routing. The microphone stream was never saved. No runtime source was changed.

Next, use repeatable synthetic input to distinguish endpointing from recognition and inspect where time is spent before cueing another phone test.
