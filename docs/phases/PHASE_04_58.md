# Phase 4.58 — Improve Motorola speech recognition

Tested offline Vosk, Whisper tiny.en, Moonshine Tiny English and a streaming Zipformer English model on the laptop. Played benchmark replies through the Motorola using the same native Sopro build and voice reference. The new recognizer heard the complete live sentence, including the words Vosk had misheard in Phase 4.57. The one live comparison did not reduce the time to speaker output.

## Recognition and endpointing

Eleven generated fixtures included three versions of the previous live phrase, a quiet final word and a one-second pause. Three bundled public speech recordings and three previously generated Sopro readings provided separate audio checks. These small sets expose failure modes rather than establish general recognition accuracy.

| Recognizer on the 11 generated clips at 1,200 ms | Word edits | Correct final words | Median batch decode |
| --- | ---: | ---: | ---: |
| Vosk | 11 | 7/11 | 1.22 s |
| Whisper tiny.en, full context | 9 | 9/11 | 1.45 s |
| Whisper tiny.en, 512 minimum audio context | 9 | 9/11 | 0.52 s |
| Moonshine Tiny INT8 | 39 | 2/11 | 0.08 s |
| Streaming Zipformer INT8 decoded from buffered PCM | 25 | 3/11 | 0.37 s |

Vosk normally processes speech during capture, so its batch timings overstate its endpoint delay. Moonshine and Zipformer did well on the public clips but did not reliably recognize the generated short turns. The 512-context Whisper configuration is a live candidate. Both the energy detector and Silero could cut off the final word on the one-second-pause fixture at shorter settings. Kept the 1,200 ms energy endpoint. The confidence fallback experiment also failed to cover all errors. Vosk assigned confidence 1.0 to the inaccurate UK synthetic phrase.

## Motorola timings

| Measurement | Vosk synthetic | Whisper synthetic | Whisper live |
| --- | ---: | ---: | ---: |
| Detected speech end to chat start | 1.73 s | 1.83 s | 1.89 s |
| Chat generation | 1.83 s | 2.08 s | 2.98 s |
| Chat completion to first Sopro PCM | 1.78 s | 1.77 s | 2.06 s |
| Detected speech end to estimated Android speaker onset | 5.40 s | 5.82 s | 7.02 s |
| Android underruns | 0 | 0 | 1 |

Both synthetic turns correctly transcribed the same WAV. Qwen generated different replies, so the full timings do not isolate recognizer speed. The live candidate recognized every expected word and Android drained all response frames. The earlier Vosk live turn took 6.88 s to speaker onset and 2.31 s to chat start. The new live turn started chat 0.42 s sooner, partly because microphone teardown overlapped recognition and chat. The transport still took about 1.07 s to stop. Synthesis waited for it to close. Differences in the chat replies limit conclusions about whole-turn speed. The two-second target remains unmet. Speaker timing uses the Android timestamp and USB clock comparison. No human PCM or transcript is stored in the phase evidence.

## Verification

- From `/mnt/data/Companion/recovery/phase_04_58`, sourced `env.sh` and ran `input-bench.py`, `public-audio.py`, `zip-bench.py`, `context-sweep.py`, `confidence-bench.py`, and `synthetic-capture.py` using the project virtual environment Python. All completed. Verified model artifact sizes and available upstream hashes. Zipformer graphs were pinned to revision `672fbf1b30579d6585301139bb363f42a0ad4a24`.
- Ran `phone-turn.py --recognizer baseline --label vosk --fixture fixtures/tea-us.wav` and the corresponding `--recognizer whisper_512 --label whisper512` turn. Both exited 0 after reconnecting the device and restaging verified temporary files. Ran `phone-turn.py --recognizer whisper_512 --label whisper512 --live` once with the owner’s cue, exit 0.
- Core voice regression subset reported 126 passed, 6 skipped. No production voice defaults or runtime files changed. The scratch runner and timing logs remain in recovery.
- Checked that the microphone process and native server stopped. Removed temporary phone files and verified zero remaining USB forwards and the restored sleep setting.

Next, overlap chat preparation with the endpoint pause only where final recognition can still reject an incorrect early transcript. Preserve the approved voice and verify the result before enabling a faster path.

[Sherpa-ONNX model documentation](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/index.html)
