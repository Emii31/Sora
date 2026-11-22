# Phase 4.57 — Live Motorola microphone and speaker timing

A live Motorola microphone turn reached local speech recognition and Qwen on the laptop, generated its reply on the Motorola with native Sopro, and played through the Motorola speaker over USB. The owner heard the live reply and rated the delivery “Same feel” compared with the approved voice. This is a one-reply listening check of the faster native backend using the same approved reference.

## Chat delay

Compared the usual voice prompt with extra guidance to speak three to seven words for simple replies. Both modes used real Qwen and native Motorola speech, with alternating order and matching starting context for each pair.

| From recognized text | Usual prompt | Brief prompt |
| --- | ---: | ---: |
| Median time to playback submission | 3.40 s | 3.34 s |
| Median chat generation | 1.23 s | 1.45 s |
| Median reply words | 6 | 5.5 |

All eight turns saved an exact exchange in disposable history. Both recall replies correctly gave the previously supplied kitten name. First-sentence boundaries would have allowed 0–1.20 s of overlap with chat generation across these turns. This is a calculated bound, since delivery still used a single whole-reply synthesis request. The small median change and mixed individual differences did not justify changing the voice prompt. The first two recall attempts exposed a harness assertion that looked at the first assistant message instead of the latest. The corrected pair checked the new exchange and expected history length.

## Motorola output

A scratch Android AAudio player received mono 24 kHz PCM, drained every response frame, and identified the built-in speaker as output device ID 3. The reported speaker times estimate presentation from Android's stream timestamp, the first speech-level PCM and USB clock calibration. There was no separate acoustic recording.

| Turn measurement | Generated input | Live Motorola microphone |
| --- | ---: | ---: |
| Detected end of speech to estimated speaker onset | 6.62 s | 6.88 s |
| From detected speech end to start of chat | 1.56 s | 2.31 s |
| Capture teardown inside the previous row | 0.31 s | 1.07 s |
| Chat generation | 2.66 s | 2.33 s |
| Chat completion to first Sopro PCM | 2.15 s | 2.04 s |
| Android underruns | 2 | 0 |

Vosk recognized the entire synthetic sentence. It misheard the live test sentence, so successful playback verifies the route while live recognition accuracy remains open. The 6.88-second live result exceeds the two-second target. The live test retained timing metadata only. No human audio or transcript was saved in the phase evidence.

## Verification and handoff

- Scratch work is in `/mnt/data/Companion/recovery/phase_04_57`. Verified the staged native executable, model assets and reference on the phone. No production source was changed.
- Ran `with-awake-phone.sh .../.venv/bin/python -B -u chat-timing.py` and `chat-timing.py --recall-only` with repository and scripts paths on `PYTHONPATH`. The first run verified six non-recall turns before the recall assertion failure. The corrected recall run exited 0 and completed both paired turns.
- Ran `phone-turn.py` with the generated input and `phone-turn.py --live` with an explicit microphone cue. Final runs exited 0. A silent output probe initially lacked presentation evidence for the final frame. A short silent tail let the Android position reach all content frames. The first live attempt ended at the cue gate because its ADB child inherited terminal input. The retry disconnected the child's stdin and opened the mic only after the gate.
- Regression tests `tests/test_liquid_live.py`, `tests/test_voice_input.py`, `tests/test_voice_brain.py`, `tests/test_voice_context.py`, `tests/test_voice_sopro_live.py` and `tests/test_voice_playback_diagnostics.py` returned 126 passed and 6 skipped.
- Confirmed the test processes stopped, no ADB forwards remained and the previous screen-sleep setting was restored. Removed the owned temporary files from the phone. Retained the approved audition app.
- Next, test a faster input path that can preserve the last word while reducing the endpoint pause and capture shutdown. Preserve the approved native delivery and measure the full speaker latency again.

[Android AAudio presentation timestamps](https://developer.android.com/ndk/reference/group/audio#aaaudiostream_gettimestamp)
