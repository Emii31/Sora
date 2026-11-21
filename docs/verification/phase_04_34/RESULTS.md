# Phase 4.34 verification

- The released config matches its Git blob hash. All three large files match their published SHA-256 hashes.
- Python compilation and the isolated environment dependency check passed.
- The audition ran with offline mode enabled and local assets in the network-restricted sandbox. The 360-second watchdog expired while generating the fourth take (exit 124). Three complete audio files and their timings were saved before the cutoff. The streaming probe did not run.
- Local Vosk recognized the complete line on both comparison takes. The playful clip retained all intended words, with one extra recognition result around the laugh cue.
- The three-take WAV is 15.22 seconds, mono 24 kHz PCM16. SHA-256 `8d7341f3051df7b2ca8f5ebc85751409af4159e2a3e339c50669ea0aa7e9e2a0`.
