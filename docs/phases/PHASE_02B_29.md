---
name: phase-02b-29
description: English Screen Memory Prompts and Writer Contract Repair
metadata:
  type: project
---

# Phase 02B.29: English Screen Memory Prompts and Writer Contract Repair

- Verify the starting checkpoint (6ff34c0081cc687b92de66d795b7860b148c3405).
- Repair screen writer empty-input contract:
  - Restore `ScreenSlotWriterOutput(skipped_reason="empty observation")` for blank observations in `memory_prompts_v3.py`.
  - Add regression test.
- Finish chat writer naming:
  - Update chat writer system prompts in `memory_prompts_v3.py` to use configured character name.
- Translate screen prompts:
  - `SCREEN_SEMANTIC_GATE_SYSTEM_PROMPT`
  - `SCREEN_SLOT_WRITER_SYSTEM_PROMPT`
  - Builder-sent text.
  - Preserve observation text and existing logic.
- Verify behavior with synthetic data and mocked model calls.
- Update documentation (`docs/phases/PHASE_02B_29.md`, `docs/SESSION_LOG.md`, `docs/VERIFICATION.md`) and publish to `origin/main`.
