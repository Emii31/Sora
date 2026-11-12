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
| **Remaining Pet & Web UI Copy** | `templates/pet.html`, `templates/index.html`, `core.py` | Pet HTML lang/chat-error fallback, invite-code sign-in, voice tooltips, clear-all confirmation dialog & backend errors | **Implemented & Verified (Phase 2)** |
| **Backend Errors & Chat Validation** | `app.py`, `core.py`, `ai_config.py`, `auth.py` | Invite-code, login/session, setup, chat blank-message, provisioning, journal, and model-connection fallbacks | **Implemented & Verified (Phase 2B.22 & 2B.23)** |
| **Main Chat Prompts & Diagnostics** | `prompt.py`, `agent_behavior.md` | Chat memory retrieval preflight prompt, shared agent behavior rules, and provider setup/connection errors | **Implemented & Verified (Phase 2B.24)** |
| **Main Chat System Prompt** | `prompt.py` | Assembled system prompt (`_build_agent_system_prompt`), reactive/proactive modes, identity, memory, images, and tool guidance | **Implemented & Verified (Phase 2B.25)** |
| **Proactive Backend Prompts & Image Compatibility** | `prompt.py` | `_PROACTIVE_RESOURCE_PLANNER_PROMPT`, `_PROACTIVE_DELIVERY_PREFLIGHT_PROMPT`, image tag markers (`[图片：...]`, `[Image: ...]`, `[图片]`), and failure sentinels | **Implemented & Verified (Phase 2B.26)** |
| **Emotion Prompts & Image Guidance Correction** | `prompt.py`, `memory_prompts.py` | User emotion annotation prompts (`EMOTION_CHAT_PROMPT`, `EMOTION_SCREENSHOT_PROMPT`, rules) and companion emotion evaluation (`_build_miru_emotion_prompt()`) | **Implemented & Verified (Phase 2B.27)** |
| **Memory Writers & Persona Stack** | `memory_prompts_v2.py`, `memory_prompts_v3.py` | Slot writers, persona writers, Pass 4 append, daily compactor, legacy merge, screen semantic gate | **Implemented & Verified (Phase 2B.28 - 2B.30)** |
| **Memory Curator Stack** | `memory_prompts_v2.py`, `curator.py` | Curator planner and merge/edit/delete executors | **Implemented & Verified (Phase 2B.31)** |
| **Journal, Diary Reformat & Bundled Persona** | `journal.py`, `prompt.py`, `soul.md` | Journal generation and empty-day fallback, diary reformat prompt, default bundled persona (Sora) | **Implemented & Verified (Phase 2B.33 - 2B.34)** |
| **Landing & Privacy Pages** | `templates/landing.html`, `templates/privacy.html` | Marketing and legal pages | **Outstanding (Deferred)** |
| **Admin Panel** | `templates/admin.html` | Administrator dashboard interface | **Outstanding (Deferred)** |
| **Comments/Docs** | Codebase-wide | Inline comments, docs | Untouched |
| **Character Config** | `data/personas/` | Persona definitions | Untouched |
| **Branding Assets** | `assets/brand/` | Logos, avatars | Untouched |

## Notes
- Phase 2A focused solely on the initial welcome/login interface in `templates/login.html`.
- Phase 2B main template translation was rolled back due to destructive truncation.
- Full system translation is deferred to future phases.
