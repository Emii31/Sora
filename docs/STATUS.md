# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 3.4 — Diagnose Local Chat Latency (Verified)
- **Current Status**: The opt-in stage timer is implemented. Four live Ollama turns saved their verified replies, with send-to-history medians of 337.85 s in full mode and 339.99 s in fast mode. The main agent call dominated both modes. All 38 focused tests passed.
- **Next Action**: Publish the verified Phase 3.4 checkpoint to `origin/main` if it has not reached GitHub. Then test a compact prompt and explicit output-token cap for the opt-in loopback fast text path. See [Phase 3.4](phases/PHASE_03_04.md) for measurements, commands, and constraints.
