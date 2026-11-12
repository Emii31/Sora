# Phase 3.2A — Shared Provider Credential and Model Selection Fixes

- **Status**: Verified & Implemented
- **Starting Checkpoint**: 6d0eb946e34c13a0dea5761a4ca59bbe3d0f8810

## Summary of Work
1. **Credential Binding (`ai_config.py`)**:
   - Resolved endpoints and credentials together.
   - Enforced that host-only configuration updates clear the previous provider's key (`api_key = ""`) to prevent cross-provider credential leakage.
   - Applied strict binding rules across shared settings, tier overrides, and environment fallback.
2. **Shared Inheritance Preservation (`ai_config.py`)**:
   - Updated `_persist_resolved_base_url()` to only persist resolved base URLs if the tier already has an explicit tier-specific host override.
   - Verified that testing an inheriting tier via `ping_tier()` does not create unwanted tier overrides, allowing chat and memory tiers to continue inheriting from shared connections.
3. **Capability-Based Model Selection & Separation (`ai_config.py`)**:
   - Removed model discovery from ordinary config reads (`_resolve_tier()`) and chat requests (`get_tier_client()`), keeping discovery strictly out of runtime paths.
   - Implemented `_discover_and_select_model()` with strict capability evidence checks: vision models require explicit vision keywords (`vision`, `vl`, `omni`, `multimodal`, `gpt-4o`, `sonnet`), and text models require text evidence (`instruct`, `chat`, `gpt`, `claude`, `qwen`, `llama`, `deepseek`, `flash`, `pro`). Ambiguous or unknown capabilities return empty models (`""`), yielding clear setup-required states.
4. **Testing & Validation (`tests/test_shared_provider.py`, `tests/test_ai_config.py`)**:
   - Added unit tests covering host-only key clearing, inheriting `ping_tier()` stability, and capability-based model selection (all 41 config and provider tests passed successfully).
5. **Next Action**: Stop after Phase 3.2A.
