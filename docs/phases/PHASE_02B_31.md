# Phase 2B.31 — English Memory Curator Prompts

- **Status**: Verified & Implemented
- **Completed Checkpoint**: 9fd7136dc7eb4e99d3197e4138272e18853136b9

## Summary of Work
1. **Curator Prompt Translation**:
   - Translated `CURATOR_PLANNER_SYSTEM_PROMPT`, `CURATOR_EXECUTE_MERGE_PROMPT`, `CURATOR_EXECUTE_EDIT_PROMPT`, and `CURATOR_EXECUTE_DELETE_PROMPT` in `memory_prompts_v2.py` to natural English with Sora/Miru branding.
   - Preserved all decision rules, JSON schemas, and self-check requirements.
2. **Configured Character Naming (`miru_name`)**:
   - Parameterized curator system prompts to use `{MIRU_NAME}` dynamically.
   - Updated call sites in `curator.py` to pass the configured `miru_name`.
3. **Verification**:
   - Ran full test suite (82/82 passed) covering all curator, slot writer, and screen gate scenarios.
