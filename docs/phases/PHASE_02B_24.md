---
name: phase-02b-24
description: English main chat prompts and provider diagnostics for phase 2B.24
metadata:
  type: project
---

# Phase 02B.24: English Main Chat Prompts and Provider Diagnostics

- Translated main chat instructions, memory retrieval preflight (`_CHAT_PREFLIGHT_PROMPT`), and JSON-only instructions in `prompt.py`.
- Translated shared agent behavior rules in `agent_behavior.md`.
- Translated provider setup diagnostics and error formatting in `_get_ai_runtime_or_raise` and `_format_ai_call_error`.
- Preserved JSON keys, enum values, tool names, memory paths, retrieval limits, routing decisions, image markers, and Sora branding.
- Verified changes with 61 focused test cases (`test_chat_preflight_routing.py`, `test_chat_error_copy.py`, `test_companion_bootstrap.py`, `test_ai_config.py`, `test_chat_archive_and_consolidate.py`).
