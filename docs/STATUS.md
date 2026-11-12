# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 2B.26 — Proactive Backend Prompts and Chat Image Compatibility (Completed & Verified)
- **Current Status**: Translated `_PROACTIVE_RESOURCE_PLANNER_PROMPT` and `_PROACTIVE_DELIVERY_PREFLIGHT_PROMPT` in `prompt.py` to natural English with Sora branding while preserving JSON contracts, enums, paths, and tool policies. Aligned system prompt image handling instructions with actual emitted markers (`[图片：...]`, `[Image: ...]`, `[图片]`) and failure sentinels (`(图片识别失败)`, `(Image description failed)`, etc.). Replaced hardcoded "Miru living with the user" with character-neutral/configured character phrasing. Added focused compatibility and structured output checks. Verified 85 tests across agent modes, attention, chat image history, preflight routing, and care engine persona suites.
- **Next Action**: Commit changes and push to origin/main.
