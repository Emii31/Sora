# Decisions

- **Documentation Structure**: Established standard set of documentation files (`PROJECT_BRIEF.md`, `ARCHITECTURE.md`, `ROADMAP.md`, etc.).
- **Baseline**: Continuing with base codebase (Miru) in `.` directory.
- **Phase 0**: Audit completed.
- **Phase 1A**: Python 3.11.18 provisional virtual environment established; isolated test baseline verified.
- **Phase 1B**: Isolated loopback smoke tester implemented and verified.
- **Phase 2A**: Welcome/login interface translated to English and rebranded to Sora (`templates/login.html`). Foreground development launcher lifecycle implemented.
- **Git Publishing Policy**: Restricted publishing exclusively to `origin` (`https://github.com/Emii31/Sora.git`). Upstream (`kiyotakali/Miru.git`) is strictly fetch-only with push disabled; local commits do not modify upstream.

- **Phase 4 offline voice input**: Use the optional Vosk runtime with an explicitly configured local model directory. Start with bounded, authenticated WAV uploads and transcript review before adding device capture or wake-word detection.

- **Phase 4 offline voice output**: Use a separately installed local Piper CLI and an explicit voice model path. The initial API synthesizes a caller-owned saved assistant reply on demand, through private temporary audio files that are cleaned after each request.

- **Phase 4 on-request camera**: Start with explicit single-frame submission and transient descriptions. Restrict frame inference to a configured loopback vision endpoint, with no route-level persistence or remote fallback.

- **Phase 6 shared memory**: Use one laptop-hosted account and its existing memory files as the canonical store. Pair the phone to that account. Defer replica management and merging independent local histories.

- **Phase 4 provisional voice choice**: Treat NeuTTS-2E's Sophie as the provisional expressive offline voice. The owner reported that it still sounds like a read line with an emotion applied and falls short of the natural delivery they want. Keep the speech provider configurable so the voice can be replaced later.

- **Phase 4 voice choice update**: The owner rejected the extended Sophie audition. Hold provider integration and use the instruction-directed Qwen VoiceDesign sample to evaluate natural delivery. The initial i5-7300U run also showed a substantial latency tradeoff.

- **Final Sora voice reference**: The owner approved the Qwen3-TTS VoiceDesign worry-to-relief take on 2026-11-17. Preserve its exact audio as the reference for future synthesis and compare changes against it. Model deployment and conversational latency are separate from the owner's final voice choice.
