---
name: phase-02b-25
description: English main chat system prompt for phase 2B.25
metadata:
  type: project
---

# Phase 02B.25: English Main Chat System Prompt

- Translated the assembled chat instructions and headings in `_build_agent_system_prompt()` (`prompt.py`) covering identity, conversation mode, relationship context, memory system, image messages, tool guidance, and authenticity rules to natural English and Sora branding.
- Translated `build_proactive_agent_user_message()` output instructions.
- Preserved character data, runtime contracts, memory paths, tool names, reactive/proactive mode distinction, and persona safety checks.
- Verified changes with 83 test cases (`test_chat_preflight_routing.py`, `test_chat_error_copy.py`, `test_companion_bootstrap.py`, `test_ai_config.py`, `test_chat_archive_and_consolidate.py`, `test_agent_modes_attention.py`, `test_care_engine_persona.py`).
