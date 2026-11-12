# STATUS

- **Project**: Sora (Companion)
- **Phase**: Phase 2B.27 — English Emotion Prompts and Image Guidance Correction (Completed & Verified)
- **Current Status**: Corrected chat image instructions in `prompt.py` to separately describe usable description tags (`[图片：...]`, `[Image: ...]`), bare tags (`[图片]`, `[Image]`), and failure sentinels (`(图片识别失败)`, `(Image description failed)`). Translated user emotion annotation prompts (`EMOTION_CHAT_PROMPT`, `EMOTION_SCREENSHOT_PROMPT`, rules, and judgment logic) in `prompt.py` and companion emotion evaluation prompt (`_build_miru_emotion_prompt()`) in `memory_prompts.py` to English while preserving JSON schemas, enums, numeric ranges, and validation. Verified all 49 emotion, agent-mode, attention, and image-history unit tests passed successfully.
- **Next Action**: Commit changes and push to origin/main.
