# Sora Translation Inventory

## Overview
This document tracks the translation of the Miru codebase to English for the Sora companion project.

| Area | Path | Scope | Status |
| :--- | :--- | :--- | :--- |
| **Welcome/Login UI** | `templates/login.html` | Visible headings, labels, buttons | **Implemented & Verified (Phase 2A)** |
| **Main UI Shell** | `templates/index.html` | App shell, nav, controls | **Rolled back / Pending Re-evaluation (Phase 2B)** |
| **Backend Errors** | Various (`app.py`, `core.py`) | Error messages, logs | Untouched |
| **Prompts/Persona** | `character.py`, `prompt.py`, `memory_prompts_v*.py` | AI personality, system prompts | Untouched |
| **Comments/Docs** | Codebase-wide | Inline comments, docs | Untouched |
| **Character Config** | `data/personas/` | Persona definitions | Untouched |
| **Branding Assets** | `assets/brand/` | Logos, avatars | Untouched |

## Notes
- Phase 2A focused solely on the initial welcome/login interface in `templates/login.html`.
- Phase 2B main template translation was rolled back due to destructive truncation.
- Full system translation is deferred to future phases.
