# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 4.32 — Motorola Liquid CPU comparison
- **Current status**: Three and four threads both took a median 1.99 seconds per second of short speech on the same four fast cores. Android narrowed some affinity masks. Both long captures had inconclusive monitor alignment, with generation at 1.75–1.80 seconds per audio second. Both fixtures retained exact PCM across runs. The four-thread default remains selected. 104 targeted tests passed.
- **Next action**: Profile the native backbone, audio decoder and vocoder separately and target the largest measured cost. See [Phase 4.32](phases/PHASE_04_32.md).
