# Architecture Audit

## Overview
Miru (the base for Sora) is a cross-platform companion application with a Python backend and multi-platform frontend (Tauri/Rust for desktop, Capacitor for Android).

## Component Breakdown

### Backend
- **Core**: `app.py`, `core.py`, `companion.py`.
- **Logic**: `care_engine.py`, `miru_emotion.py`, `attention_engine.py`.
- **Storage/Memory**: `storage.py`, `core_memory.py`, and `memory.py` manage persistent data using JSON files stored in a directory-structured file system (defaulting to `data/`). Key storage paths include `timeline.json`, `chat_history.json`, and various log files (`emotion_log.json`, `attention_log.json`).
- **AI Configuration**: `ai_config.py` manages a 3-tier system (vision, chat, memory), storing admin-managed credentials in `data/_admin/ai_config.json`.
- **Launcher**: `linux_launcher.py` (X11 only, explicitly rejects Wayland via `x11_session_available()`), `miru_launcher.py`.

### Desktop
- **Frontend**: Tauri-based shell (`src-tauri/`).
- **Preview**: PySide6/Qt Linux preview (`linux_pet.py`, `windows_launcher.py`).

### Mobile
- **Android**: Capacitor/native Android client (`miru-mobile/`).

### Communication
- Uses a mix of SSE (`sse.py`), API tools, and local memory databases.

## Known Unknowns / Unverified Behavior
- **Local Inference Routing**: Routing and offline capabilities remain undecided. `ai_config.py` handles provider settings; `model_library.py` contains character/avatar models and should not be confused with language-model routing.
- **Wayland Compatibility**: `linux_launcher.py` explicitly rejects Wayland.
- **Python Version**: Upstream baseline requires Python 3.12. Compatibility with other versions (such as local Python 3.11/3.14) is unverified.
- **Third-party Assets**: Live2D files are missing/not redistributed in the public source.

## Audit Findings (Representative Paths)
- **Startup**: `linux_launcher.py` -> `windows_launcher.py` -> `desktop_main()`.
- **Memory**: `storage.py` provides atomic JSON read/write helpers and directory management; `core_memory.py` manages higher-level memory state.
- **Chinese Text/Branding**: Potential hardcoded Chinese strings and assets in `assets/brand/` or duplicated UI templates. Need to audit `assets/js/` and templates.

## Offline voice input

The backend's authenticated `POST /api/voice/transcribe` route accepts short mono PCM WAV uploads. `voice_input.py` validates the format and calls the explicitly configured local Vosk model. Clients receive a transcript in the response and use the regular chat route when the user sends it.

## Offline voice output

The authenticated `POST /api/voice/synthesize` route resolves a saved assistant reply in the caller's recent chat. `voice_output.py` passes the text on stdin to the configured local synthesizer and returns a WAV. `SORA_QWEN_VOICE_DIR` selects the approved voice using Qwen3-TTS Base and a pre-encoded reference. Without that setting, Piper uses its existing explicit model path and pacing presets. The client owns playback timing and interruption.

## On-request camera input

The authenticated `POST /api/camera/describe` route takes one still frame and returns a description. `camera_input.py` normalizes the frame in memory and calls the configured loopback vision model directly. Client code owns capture and device permissions. The description is returned only to the request caller.

## Shared memory

Connected devices can read and update one account's memory through the laptop's authenticated APIs. The account determines the storage directory for Markdown, slots, core memory, and chat history. Clients revalidate cached reads against the backend. The opt-in pairing backend issues an independently revocable phone credential for the existing laptop account. The backend has separate owner loopback and scoped phone HTTPS listeners. Both USB and direct private Wi-Fi transport were verified with a physical Motorola. Persistent trust and ordinary Android client integration remain deployment work.

## Personality in full and fast chat

Both chat modes use the active character. The full agent adds core memory and relationship context. The fast loopback prompt uses a compact persona, recent turns, and bounded excerpts of the active account's human and relationship core memory. Speech uses the saved reply and a caller-selected Piper delivery preset.

## Phase 4.26 live Liquid terminal prototype

`scripts/live_liquid_voice.py` coordinates laptop microphone capture, optional incremental Vosk recognition, the phone's Liquid streaming server, and buffered PipeWire playback. `voice_liquid_live.py` contains the cancellable stream and audio components. `scripts/liquid_phone.py` manages verified model caching, the owned Android runner, its CPU affinity and an ADB loopback forward. Enter cancels the current turn and begins listening again. Each prototype reply currently uses a reset context and the selected default interleaved chat voice. Integrating active-character context and account memory is the next backend phase.

## Phase 4.27 account-scoped live voice

The terminal now transcribes input locally, loads a `LocalVoiceContext` snapshot, requests a complete reply from `LocalVoiceBrain` using the existing loopback chat provider, and streams forced-text Liquid speech on the phone. The runner patch keeps the selected audio model and interleaving mode. Existing identity/core memory and bounded chat are read from the selected account; completed exchanges append to the same history under thread/process transaction locks. No new memory store, remote provider fallback or voice-controlled device tools are introduced. Recognition and voice synthesis are cancellable; the phone runner and ADB forward remain session-owned. See Phase 4.27 for measured delays and limitations.

## Phase 4.28 voice startup and playback policies

`LocalVoiceContext.warmup()` sends a one-token request through the existing loopback brain before the CLI listens. It does not append history. `LocalVoiceBrain` reports time to first token and completion; normal replies retain complete-response validation. The voice-only prompt removes duplicated instructions while preserving context sources and limits. `voice_playback_buffer()` selects short-reply streaming reserves; an explicit smooth-long option collects bounded PCM until generation ends before opening playback. Fixed buffer overrides take precedence. Setup warmup and per-turn timing are recorded separately in requested diagnostic reports. No synthesizer model, PCM rate or generation protocol changes were made.

## Phase 4.29 experimental sentence pipeline

An optional callback in the local brain feeds a conservative sentence buffer and bounded four-item queue. A dedicated speech worker synthesizes segments sequentially into one playback process while the brain continues. The coordinator retains the original completed reply and commits one exchange only after all stages succeed. Failure aborts the other connection; user cancellation stops and joins both workers. The private runner resets output modality and pending PCM at turn start, including after an aborted request. Sentence-level synthesis still resets model context per request and changes generated waveform/cadence; it remains off by default pending continuity and quality work.

## Phase 4.30 continuous text-to-speech session

`--continuous-speech` connects the local brain's raw text callback to one native Liquid inference job. `ContinuousLiquid` owns a per-turn input ID and separate SSE/control connections; small append-only updates share the same backbone and vocoder state. The native server retains one inference worker with three HTTP handlers for stream/input/cancel, and limits input/session activity. Prefix token checks prevent partial-word retokenization from changing accepted tokens. Final text is closed only after valid brain completion; both stages and playback must succeed before history is appended. The speaker uses the original user text for context. Defaults, model weights, existing app voice routes and account storage remain unchanged.

## Phase 4.31 playback diagnostics

An optional profiler creates and owns a dedicated virtual sink and recorder, sends fixed synthetic input through the existing phone runner and playback writer, and aligns the monitor recording to reference PCM. It also records phone process CPU time, thermal snapshots and chunk arrival timing. NumPy is isolated to the optional diagnostics requirements.

## Phase 4.32 phone CPU benchmarking

The phone runner accepts a validated per-session CPU mask and thread count. The benchmark applies each profile to both prefill and generation, captures playback through the virtual monitor, records affinity snapshots and checks exact PCM hashes. The terminal's ordinary runner uses its existing four-thread configuration.
