# PHASE 1B: Isolated Local Backend Smoke Test (Repaired)

**Goal:** Demonstrate that the existing backend can serve its web interface on this laptop using the provisional Python 3.11 environment.

**Status:**
- [x] Legacy test script executed directly (`.venv/bin/python tests/test_identity_aliases_cascade.py`): **34/34 passed**, exit code `0`.
- [x] Repaired smoke test launcher created (`scripts/dev_local_smoke.py`).
- [x] Runtime data isolated via managed disposable `DATA_DIR` with `atexit` cleanup.
- [x] Listening address verified: bound exclusively to `127.0.0.1:5000` (socket ownership verified).
- [x] HTTP checks verified:
  - `/api/health` -> `200 OK` with valid JSON (`{"ok":true,...}`).
  - `/` -> `200 OK` (Landing/Marketing page, 36KB).
  - `/app` -> `200 OK` (Companion interface HTML, 490KB).
- [x] Server shutdown verified cleanly (SIGINT captured, temporary directory cleaned up).

**Verification Results:**
- Socket: `127.0.0.1:5000` (exclusive to python process).
- Health API: `200 OK` (JSON confirmed).
- Landing page (`/`): `200 OK`.
- Companion app (`/app`): `200 OK`.
- Browser rendering: Pending (no browser automation tool available; HTTP structure confirmed).
- Missing assets: Live2D assets remain missing (expected per upstream design).
- Offline dependencies: External font/CDN resources referenced in HTML remain as unresolved offline requirements.

**Conclusion:** Phase 1B repair and verification completed successfully.
