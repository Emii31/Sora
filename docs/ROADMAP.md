# Roadmap

- **Phase 0**: Workspace/Audit (Completed)
- **Phase 1**: Reproducible Arch baseline (Completed)
- **Phase 2**: English/Sora branding (Completed)
- **Phase 3**: Unified provider and local-inference benchmark (Phases 3.1, 3.1A, 3.1B, and 3.2 Shared Provider Configuration and Automatic Model Selection Completed & Verified)
- **Phase 4**: Voice/personality/on-request camera (4.1–4.7 cover transcription, synthesis, an offline voice turn, speech delivery presets, submitted-clip wake detection, and the camera frame API verified with local Moondream. 4.8 audited personality context and reran the offline voice chain. 4.9 added bounded core memory to fast chat. 4.10 refined the bundled persona. 4.11 generated Piper samples. 4.12 tested an expressive offline model. 4.12A auditioned three female voices. 4.13 auditioned Supertonic 3. 4.14 compared NeuTTS-2E emotions. 4.15 auditioned a continuous, instruction-directed Qwen VoiceDesign take. 4.16 connected that approved reference to the local speech backend. Device capture checks remain pending.)
- **Phase 5**: 3D avatar/island interface (Deferred to the app stage at the owner's request.)
- **Phase 6**: Android/shared memory (6.1 audited the backend. 6.2 verified independent pairing, durable shared reads, and recall over USB. Protected private Wi-Fi deployment is next.)
- **Phase 7**: Device tools/tasks (Deferred)
- **Phase 8**: Controlled skill learning and self-improvement (Deferred)

## Unresolved Design Issues (Phase 1+)
- Wayland desktop overlay/capture support (Major blocker for Linux desktop pet).
- Project-local Python 3.12 versus testing newer Python (currently using 3.14.9).
- Missing third-party avatar assets.

## Current backend checkpoint — 2026-11-20

Phase 4 continues. Later auditions selected the Liquid interleaved voice for the terminal prototype. Phases 4.26–4.28 connected live capture, persona/memory, startup warmup and latency controls. Phase 4.29 tested optional sentence resets but found quality/completion regressions. Phase 4.30 added optional continuous speech context and verified waveform parity, earlier starts, memory and recovery. These are terminal/backend changes; existing app speech routes and the app/3D-avatar stage remain separate.

Next proposed work is Phase 4.31, measuring actual playback continuity and phone throughput before promoting a voice mode. Do not jump to Phase 5 or resume Phase 6 without the owner's instruction. Consistent two-second conversation, reliable recognition, natural barge-in and owner approval of delivery remain open. The active project environment is the existing Python 3.11.18 virtual environment; the older system-interpreter note above is not a requirement to replace it.

Phase 4.31 added calibrated digital playback capture and phone profiling. The measured speech generator ran below playback speed. The next backend experiment is inference throughput on the selected voice, followed by repeat digital continuity checks.

Phase 4.32 compared CPU placement and thread count using identical synthetic speech. Android changed some requested masks despite periodic reapplication. Throughput work should distinguish time in the native backbone from time in audio decoding and vocoding before changing the terminal's defaults.

Phase 4.33 separated Liquid's native stages and measured stock offline alternatives. Piper Amy Low has verified speech throughput on the laptop. Owner review and full conversation latency remain separate checkpoints.
