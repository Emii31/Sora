# PHASE 02B_5: System Account & Desktop-Preference Translation

**Goal:** Translate frontend-owned UI strings in System Account and Desktop-Preference settings panel.

**Status:**
- [x] Invitation code label, copy button, status messages, copy feedback translated.
- [x] Desktop-pet shortcut, controls, hide-delay label/help translated.
- [x] System settings Save button/feedback translated.
- [x] Account heading, retention explanation, Switch Account button/confirmation translated.
- [x] All preservation checks (script/style blocks, IDs, handlers, line count) pass.
- [x] Syntax validated.

**Evidence:**
- Changed in `templates/index.html`: `_loadSettingsInvitationCode`, `_copySettingsInvitationCode`, `settingsSwitchAccount`, `_fmtScreenshotTime`, `_loadScreenshotStats`.
- Preservation checks: Script/Style blocks verified identical (with authorized exceptions).
- Line count: 12807 (unchanged).
- Backup: `/mnt/data/Companion/recovery/20261108_device_backup/index_before_phase_2B_5_patch.html`.

**Next Steps:** None authorized.
