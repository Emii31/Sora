# PHASE 02B_9: Chat Controls, Frontend Feedback Translation, and First-Run Deployment Fix

**Goal:** Translate frontend-owned UI strings, repair first-run deployment regression (`miru/server:0.2.0`), and restore strict test specificity.

**Status:**
- [x] Chat composer placeholder and Send button translated.
- [x] Voice-input tooltip translated.
- [x] Companion-panel heading and controls (Refresh, Collapse) translated.
- [x] New-message indicator translated.
- [x] All dynamic UI feedback updated to reflect English translations.
- [x] Restored `miru/server:0.2.0` image default in input and JS fallback.
- [x] Restored explicit test assertions for image defaults, scoped `<h1>API Key</h1>`, port selection, and prior deployment task checks in `tests/test_first_run_wizard.py`.
- [x] Test suite passed (`tests/test_first_run_wizard.py` and `tests/test_chat_error_copy.py`).
- [x] Git history prefix integrity enforced (pre-commit check passed against `e40d2db`).

**Evidence:**
- Changed in `templates/login.html`: Restored `miru/server:0.2.0` image default and JS fallback.
- Changed in `tests/test_first_run_wizard.py`: Explicit image default assertions, scoped `<h1>API Key</h1>`, port selection and task checks.
- Test results: `docs/verification/phase_02B_9_deploy_fix/test_results.txt`.
- Git diff check: PASS.
- History integrity: `scripts/check_history_append_only.py` verified.

**Next Steps:** None authorized.
