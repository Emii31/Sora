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

- **Phase 4.16 voice runtime**: Use the approved reference waveform with the CPU build of Qwen3-TTS 0.6B Base. Pre-encode the reference once, keep runtime files and weights outside Git, and select the voice with `SORA_QWEN_VOICE_DIR`. Its reference-driven delivery has no independent acting presets.

- **Current Sora voice reference and phone trial**: The owner selected Liquid Audio's default interleaved chat voice from the tone-comparison audition. Phase 4.25 verified that the Motorola Snapdragon SM6450 phone can run this model, with lower measured delays than the laptop. Treat phone inference as a candidate for the next live prototype. Continue evaluating real conversation latency and response quality before production integration.

- **Phase 4.26 live prototype**: Use a standalone terminal process with phone-local Liquid inference over a USB forward, local Vosk recognition and PipeWire capture/playback. Enter explicitly interrupts a turn. Keep the selected Liquid voice while validating context integration in the following phase. Verified model files stay in the phone's dedicated cache, and owned services stop when the terminal session closes.

- **Phase 4.27 voice context**: Compose replies using the configured loopback chat model and the active account's compact persona, identity, core memory and recent chat. Speak that text with the selected Liquid interleaved model through a private forced-text runner patch. Direct Liquid chat failed factual recall probes. Save completed exchanges in existing history; cancelled/failed exchanges are excluded. The installed Qwen chat model replaces the unavailable local `llama3` selection. This is a correctness integration, not a claim of two-second conversation latency or automatic long-term memory extraction.

- **Phase 4.28 latency controls**: Prefill the configured local chat model before listening, report startup separately, and shorten duplicated voice prompt instructions without cutting saved context budgets. Automatically use a smaller reserve only for short replies. Keep streaming as the default for longer speech; complete-audio buffering is opt-in with `--smooth-long-replies` because its measured start delay is too large for the default conversation path. Fixed buffer overrides remain available. The selected Liquid waveform and model are unchanged; two-second conversation and universally smooth streaming remain unverified.

- **Phase 4.29 experimental streaming**: Keep sentence streaming opt-in. A bounded producer/consumer pipeline starts speech before the local brain completes and saves only fully completed turns. It improves controlled start times but can increase duration, change cadence and possibly repeat audio, so whole-reply mode remains the default. A private native reset now clears audio modality/PCM after interruption, verified by cancellation/recovery. Continuous speech context and conversational conditioning require further investigation before promotion.

- **Phase 4.30 continuous speech context**: Add an optional single-session text feed rather than resetting the speech model per sentence. Incremental and whole-context audio matched byte-for-byte in the tested fixtures, with earlier starts and shorter completion than the matched baseline. Preserve the default until listening and real continuity checks pass. Use only complete stable token prefixes, explicit finalization, bounded input and owner-session cancellation; tolerate brief native cleanup lag through bounded HTTP-409 retry. Real-time playback and recognition remain unresolved.

- **Phase 4.31 playback diagnostics**: Use captured virtual monitor PCM and reference waveform alignment to verify added playback time. Treat pipe estimates separately and report inconclusive captures explicitly. Full buffering is a useful control with a substantial startup cost. Prioritize synthesis throughput over a new buffer default.

- **Phase 4.32 CPU profiles**: Keep alternate affinity and thread counts available to the benchmark. Compare identical PCM and require repeatable throughput and monitor continuity before adopting a profile for conversation.

- **Phase 4.33 stock voice audition**: Piper Amy Low passed the laptop speech speed checks at factory settings. Keep her as an audition candidate pending the owner's listening review. The complete turn's dominant delay now comes from the local chat model in the measured alternate path.

- **Phase 4.34 voice audition** The owner rejected Piper Amy Low's delivery. Stock KittenTTS 2 is a listening candidate only. Its measured runtime on the laptop rules it out for live use.

- **Phase 4.42 phone speech**: Keep Gwen’s stock weights and delivery controls. Use a 256-frame chunk ceiling and prime short and longer synthesis before accepting a request. Keep the USB worker experimental until a microphone-to-speaker check verifies complete conversational latency and playback continuity.

- **Phase 4.45 voice selection**: The owner approved the full Liquid conversation reel. Its exact playback audio is the reference for delivery across moods. The Gwen and Supertonic trials did not meet the owner’s delivery preference. Voice quality is approved for the reference and live performance remains a separate acceptance check.

- **Phase 4.46 performance**: Keep the approved Liquid reel. The stock Motorola runner missed the speed target even with complete text input. The tested KleidiAI build returned invalid speech and is ruled out for this runner.

- **Phase 4.49 Sopro integration**: Keep Sopro an explicit terminal option using the approved Liquid reference. One-turn microphone and speaker wiring is verified. Promotion depends on accurate recognition, reliable endpointing and acceptable full-turn latency.

- **Phase 4.55 Motorola voice quality baseline**: The owner approved the three on-device Sopro LiteRT readings. Use the exact audition build, reference and seed sequence as the comparison baseline for phone optimization. Accept slower laptop delivery. The first-PCM wait on the Motorola remains 12.11–15.76 seconds and live speed is unverified.

- **Phase 4.56 Motorola acceleration**: Keep the approved LiteRT build as the listening reference. Native ARM streaming is a faster experimental candidate with identical generated PCM in its two- and three-thread tests. Approval requires listening on the phone and a measured live turn.

- **Phase 4.57 native Motorola listening check**: The owner reported “Same feel” for the measured native live reply. Preserve the reference and native synthesis settings for latency work. The abbreviated chat prompt remains experimental because its median gain was small. The live route needs faster input handling and more accurate recognition.

- **Phase 4.58 speech input**: Retain the 1,200 ms pause for the experiment because shorter settings clipped a hesitation. Treat the reduced-context Whisper recognizer as a candidate following its correct live test. Keep production settings and the approved synthesis path while testing latency.

- **Phase 4.59 reply preparation**: Keep early reply preparation experimental. Require an exact final transcript and context match, discard the draft on resumed speech and wait for finalization before synthesis or persistence. Profile the approved native voice startup before selecting another latency optimization.

- **Phase 4.60 native synthesis profiling**: Preserve the approved Sopro configuration. Evaluate improvements in the first acoustic stage with multiple fixed lines and exact PCM parity before measuring any candidate on the speaker.

- **Phase 4.61 acoustic startup**: Keep the graph cache out of the voice path. Treat faster-core scheduling as a Motorola-only experimental profile pending playback continuity and full-turn verification.

- **Phase 4.62 Motorola playback**: Keep priming and the 0.75-second buffer as an experimental continuity configuration. The two synthetic recordings had zero reported underruns but cover only one sentence. Work on earlier safe delivery of a full sentence while preserving the approved voice and verifying playback.

- **Phase 4.63 sentence delivery**: Keep whole-reply Sopro synthesis as the default. Independent synthesis calls shortened speaker onset but introduced underruns at sentence boundaries. Keep the sentence scheduler experimental and prioritize reducing complete-reply preparation time.

- **Phase 4.64 local Qwen threads**: Treat four threads as an experimental setting for this laptop's native Ollama voice route. Keep one Sopro request per reply and verify sustained multiturn behavior before enabling the profile by default.

- **Phase 4.65 Ollama opt-in**: Expose native Ollama thread selection only through the terminal voice flag for a direct local connection. Keep the default chat protocol and whole-reply Sopro delivery. Measure later-turn context costs before changing conversation defaults.

- **Phase 4.66 voice latency**: Stop incremental tuning of the current three-model pipeline for the two-second target. Keep the owner-approved voice available. Any separate offline architecture needs both an on-phone timing pass and owner acceptance of the delivery.

- **Phase 4.67 LFM3 screen**: Reject the tested LFM3-Audio Q4_0 CPU pairing for live Motorola use. Use speech-level PCM and continuous delivery as speed gates before asking the owner to evaluate another voice.
