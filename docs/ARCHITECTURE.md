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
