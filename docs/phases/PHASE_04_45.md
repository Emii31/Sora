# Phase 4.45 — Owner-approved Liquid voice reference

The owner approved the full 42.5-second reel for Sora’s voice and emotional delivery. Use the entire reel for listening comparisons. It contains Liquid’s conversational responses to good news, a cookie joke and a request for reassurance. The original, untrimmed audio is the reference. Do not substitute a dedicated TTS preset or select only one mood.

- Approved local copy: `/mnt/data/Companion/recovery/voice-reference/sora-approved-liquid.wav`
- SHA-256: `20998802025caa81a3263a1554ecaf23c63923f761f1d3e68d50d87024ee8206`
- Format: PCM16 mono at 24 kHz
- Reply starts: 0.00, 10.10 and 26.92 seconds
- Provenance: Liquid LFM2.5-Audio-1.5B Q4_0, with the saved Phase 4.22 model bundle and CPU runner. The model produced each reply in interleaved conversation mode from a local synthetic spoken prompt. Generation and verification scripts are under `/mnt/data/Companion/recovery/phase_04_45`.

All three turns reached a stop event and the assembled PCM is byte-identical to the source takes with one second of silence between replies. On the i5-7300U, the first PCM arrived in 2.44–3.09 seconds. Complete replies took 19.69–31.54 seconds. These times exclude microphone capture and playback and do not establish live-chat readiness.

The next performance test should keep this approved reel as the listening baseline and measure audible startup, continuous playback, and full microphone-to-speaker latency on the device. Keep the application voice configuration unchanged until a test establishes both delivery acceptance and conversational speed.
