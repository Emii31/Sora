# Sora Translation Inventory

## Overview
This document tracks the translation of the Miru codebase to English for the Sora companion project.

| Area | Path | Scope | Status |
| :--- | :--- | :--- | :--- |
| **Welcome/Login UI** | `templates/login.html` | Visible headings, labels, buttons | **Implemented & Verified (Phase 2A)** |
| **Main UI Shell** | `templates/index.html` | App shell, nav, controls | **Static navigation translated (Phase 2B.1)** |
| **Identity Settings** | `templates/index.html` | Identity settings panel & feedback | **Implemented & Verified (Phase 2B.2)** |
| **AI Models Settings** | `templates/index.html` | AI configuration settings panel | **Implemented & Verified (Phase 2B.3)** |
| **Devices Settings** | `templates/index.html` | Devices settings panel | **Implemented & Verified (Phase 2B.4)** |
| **System Settings** | `templates/index.html` | Account & desktop preferences, hotkey/save feedback, screen observation & wallpaper | **Implemented & Verified (Phase 2B.5 & 2B.6)** |
| **Chat Controls** | `templates/index.html` | Composer, voice input, companion panel, feedback | **Implemented & Verified (Phase 2B.9)** |
| **Memory Browser Overview** | `templates/index.html` | Domain tabs, slot cards, empty/loading states, quick entries | **Implemented & Verified (Phase 2B.11)** |
| **Memory Detail View & Actions** | `templates/index.html` | Slot detail view, delete/archive confirmations, edit modal, merge dialog | **Implemented & Verified (Phase 2B.12)** |
| **Core Portrait & Journal Views** | `templates/index.html` | Core portrait view, journal list, journal book reader, highlights, stats, sharing/export copy | **Implemented & Verified (Phase 2B.13)** |
| **Commitments & Journal Localization** | `templates/index.html` | Commitments (DDL) tracker overview/list/form, Journal English date formatting (`_journalFormatDate`) | **Implemented & Verified (Phase 2B.14)** |
| **Android Native & Desktop Pet Copy** | `miru-mobile/android/...`, `templates/pet.html` | Connection, screen capture, quick replies, APK update, startup errors, desktop pet default character fallback | **Implemented & Verified (Phase 2B.20)** |
| **Backend Errors** | Various (`app.py`, `core.py`) | Error messages, logs | Untouched |
| **Prompts/Persona** | `character.py`, `prompt.py`, `memory_prompts_v*.py` | AI personality, system prompts | Untouched |
| **Comments/Docs** | Codebase-wide | Inline comments, docs | Untouched |
| **Character Config** | `data/personas/` | Persona definitions | Untouched |
| **Branding Assets** | `assets/brand/` | Logos, avatars | Untouched |

## Notes
- Phase 2A focused solely on the initial welcome/login interface in `templates/login.html`.
- Phase 2B main template translation was rolled back due to destructive truncation.
- Full system translation is deferred to future phases.
