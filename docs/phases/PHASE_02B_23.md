---
name: phase-02b-23
description: Backend copy cleanup and benchmark error detection for phase 2B.23
metadata:
  type: project
---

# Phase 02B.23: Backend Copy Cleanup and Benchmark Error Detection

- Translated blank-message response in `POST /api/companion/chat` (`"Please enter a message"`).
- Updated internal vision/image description failure message (`"(Image description failed)"`) and proactive trigger image tag (`"[Image: ...]"`) in `core.py`.
- Fixed `scripts/benchmark_chat.py` failure detection to correctly count English fallback responses introduced in Phase 2B.22 as failed turns even when saved, while allowing valid replies containing the word "error" to pass.
- Verified changes with focused companion, chat-error, and routing test suites (25 unit tests passed).
