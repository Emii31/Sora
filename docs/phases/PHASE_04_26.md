# Phase 4.26 — Live Liquid Voice Prototype

## Status

Verified as a terminal prototype on 2026-11-20. The prototype uses the owner's Android phone for Liquid generation and the laptop's PipeWire devices for capture and playback. The owner confirmed hearing its response during the live microphone test.

## Run

The phone must be connected and authorized through USB debugging. The runner and four model files from Phase 4.25 must exist under the local Liquid kit. The optional recognizer uses the existing local English Vosk model. Its pinned Python package was installed into the project's `.venv` during this phase.

```bash
cd /mnt/data/Companion/Miru
PYTHONPATH=. .venv/bin/python -B scripts/live_liquid_voice.py \
  --kit /mnt/data/Companion/sora-liquid-audition \
  --vosk-model /home/imam/Projects/openwakeword-train/model/en/vosk-model-small-en-us-0.15
```

Speak when the terminal displays Listening. Pause about a second to submit the sentence. With Vosk enabled, the terminal displays the recognized text and sends it to Liquid's interleaved chat mode. Enter interrupts capture, generation or playback and starts another turn. Type `q` and Enter, or press Ctrl+C, to close the session. `--once` runs a single microphone turn. `--replay <wav>` exercises real phone generation and playback with a prerecorded 16 kHz mono PCM16 input.

## Components and boundaries

- `voice_liquid_live.py` provides bounded microphone capture, silence endpointing, optional incremental local recognition, cancellable HTTP streaming and buffered PCM playback.
- `scripts/liquid_phone.py` verifies the local models and Android cache, starts the loopback runner, creates an ADB forward, maintains the runner's CPU affinity and closes its processes and forward afterward.
- `scripts/live_liquid_voice.py` provides terminal controls, per-turn cancellation and timing output. `--source`, `--sink`, `--threshold` and `--buffer-seconds` control the local audio path. A 1.5-second audio prebuffer is the default.

The terminal prototype uses the selected default Liquid chat voice and the same minimal interleaved system prompt as the benchmark. Each reply starts from a reset model context. Sora's persona, memory, existing application chat routes and speech-to-interrupt echo cancellation remain integration work for the following phase. Enter provides explicit interruption while the microphone is inactive during generation and playback.

Input WAVs remain in memory by default. Temporary server logs are removed on exit. An explicit fresh `--report` directory saves diagnostic logs, which can contain conversation text, and numeric timing results. About 1.2 GB of verified runner/model files remain in `/data/local/tmp/sora-liquid-live` to avoid copying them for every session.

## Verification findings

The initial real playback exposed Android narrowing the runner's affinity after loading. The launcher now reapplies cores 4–7 once per second only while its owned runner process is active. The guarded replay began buffering into PipeWire at 4.18 seconds and finished without an estimated playback gap. These timing values describe submission to the playback pipe, rather than physical sound reaching a listener.

An initial synthetic capture used a monitor name that did not resolve to an explicit PipeWire source. The corrected test creates an explicit remapped virtual microphone. A known recording also revealed that the original 650 ms cutoff split an internal pause. The 900 ms cutoff preserved both clauses, and local recognition returned `i got the job congratulate me in a few words`.

The owner's first direct-audio microphone trial produced an unrelated answer. A subsequent recognized-input trial returned no utterance, and the owner confirmed that they missed the listening window. A continuously listening session then recognized `how are you today` and answered `I'm doing well, thanks for asking. How can I help you today?`. The owner confirmed hearing the reply. First audio arrived 1.03 seconds after capture/recognition, and buffered playback began at 2.97 seconds. These figures exclude speech duration and the approximately 900 ms endpoint pause. The two-second end-of-speech target remains unmet.

## Completed checks

The corrected explicit virtual-microphone test recognized the complete fixture, sent it to the phone, and started real PipeWire playback at 2.96 seconds after capture/recognition. Cancelling a subsequent active reply stopped its audio and worker within 0.010 seconds. A fresh turn completed successfully afterward.

The keyboard test exposed ADB consuming terminal input inherited from the launcher. Microphone and ADB child processes now receive disconnected stdin. Pseudo-terminal tests verified Enter interruption and `q` exit through the actual CLI. Both exited 0, with stop-and-cleanup times of 0.717 and 1.192 seconds. These include phone teardown and are separate from the active-audio cancellation measurement.

Longer live replies showed estimated playback starvation with the fixed 1.5-second prebuffer. The gap estimator was corrected to advance its playback clock after a late chunk, and a focused regression covers that behavior. Continuous playback for all reply lengths and consistent two-second responses remain future work. Smaller buffers trade earlier playback for a greater risk of gaps.

The focused regression command was `PYTHONPATH=. .venv/bin/python -B -m pytest tests/test_liquid_live.py tests/test_voice_input.py -q`. Result was 59 passed, 6 skipped, exit 0. `.venv/bin/python -m pip check` reported no broken requirements. The optional dependency install affected only the project virtual environment.

All owned test sessions, ADB forwards, microphone/playback subprocesses and temporary virtual audio modules were stopped. The phone runner lock was removed. The verified cache remains on the Motorola phone and occupied 1,137 MiB at cleanup. Temporary human-session logs were removed and raw human microphone audio was not saved.

## Evidence and next action

Committed evidence is under `docs/verification/phase_04_26/`. Local synthetic test recordings and diagnostic logs are under the conversation artifacts' `sora-liquid-audition/live-prototype/` directory. Early failed attempts remain documented separately from the successful corrected tests.

Next is Phase 4.27, integrating Sora's actual persona and memory into the phone conversation path and checking identity, response quality, longer-reply playback and latency through that context pipeline. Wake-word activation and acoustic echo cancellation need their own device verification.
