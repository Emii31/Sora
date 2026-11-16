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

Connected devices can read and update one account's memory through the laptop's authenticated APIs. The account determines the storage directory for Markdown, slots, core memory, and chat history. Clients revalidate cached reads against the backend. Pairing to the existing laptop account and private network transport are separate requirements for deployment.

## Personality in full and fast chat

Both chat modes use the active character. The full agent adds core memory and relationship context. The fast loopback prompt uses a compact persona, recent turns, and bounded excerpts of the active account's human and relationship core memory. Speech uses the saved reply and a caller-selected Piper delivery preset.
