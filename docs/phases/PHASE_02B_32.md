# Phase 2B.32 — English Memory Append, Compaction, and Merge Prompts

- **Status**: Verified & Implemented
- **Completed Checkpoint**: 253579ed147462bd542f43c03bbe948bc417da79

## Summary of Work
1. **Slot Maintenance Prompt Translation**:
   - Translated Pass 4 append prompts (`PASS4_APPEND_SYSTEM_PROMPT` and `PASS4_APPEND_USER_TEMPLATE`), daily compactor prompts (`SLOT_DAILY_COMPACTOR_SYSTEM_PROMPT` and `SLOT_DAILY_COMPACTOR_USER_TEMPLATE`), and legacy slot merge rewrite prompts (`LEGACY_SLOT_MERGE_SYSTEM_PROMPT` and `LEGACY_SLOT_MERGE_USER_TEMPLATE`) in `memory_prompts_v2.py` to natural English.
   - Preserved all JSON fields, enums, limits, paths, retry behavior, file write contracts, and literal references to `## 近期记录`.
2. **Configured Character Naming (`miru_name`) Integration**:
   - Added `{MIRU_NAME}` parameterization to Pass 4, daily compactor, and legacy merge system prompts.
   - Added `_load_miru_name()` helper and `miru_name` parameter support to `call_pass4_append_slot`, `call_slot_daily_compactor`, and `call_legacy_slot_merge_rewrite`.
3. **Verification**:
   - Ran all unit tests across curator, Pass 4, slot daily compactor, slot writing, and cost routing suites (85/85 passed successfully).
   - Updated test assertions in `tests/test_slot_daily_compactor.py` and `tests/test_pass4_summary_truncate.py`.
