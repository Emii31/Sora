---
name: phase-02b-27
description: English emotion prompts and image guidance correction for phase 2B.27
metadata:
  type: project
---

# Phase 02B.27: English Emotion Prompts and Image Guidance Correction

- Correct chat image instructions: specifically differentiate usable description tags vs. bare tags/failure sentinels ([Image], [图片], [Image: (Image recognition failed)]).
- Update compatibility test to catch contradictory instructions.
- Translate backend emotion prompts in `prompt.py` and `memory_prompts.py` to English.
- Preserve configuration, JSON contracts, and numeric ranges.
- Update documentation and publish.
