# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 4.28 — Voice Startup and Playback Latency Controls
- **Current Status**: Verified cold prefill before Listening, compact voice instructions, first-token diagnostics and earlier short-reply buffering. Identity/core-memory/restart checks still pass; measured playback starts were 3.88–7.13 s after recognition, following 16.85 s cold startup. Long smooth playback is optional because waiting for complete audio adds substantial delay. Streaming gaps and recognition mistakes remain; two-second live conversation is unachieved.
- **Next Action**: Proposed Phase 4.29: investigate sentence-boundary speech pipelining while retaining complete-turn persistence, interruption and the selected Liquid voice. App work remains deferred. See [Phase 4.28](phases/PHASE_04_28.md).
