# Session Log

## 2026-11-07 (Phase 2A Completed)
- Repaired `scripts/dev_local_smoke.py` to use a foreground Flask execution lifecycle with proper error propagation and `finally` cleanup.
- Created `docs/TRANSLATION_INVENTORY.md` to map UI translation scope and progress.
- Translated and rebranded the initial welcome/login interface (`templates/login.html`) to English and Sora branding.
- Verified `/api/health`, `/app`, and `/login` via isolated smoke test runs. Saved command evidence under `docs/verification/phase_02A/`.
- Updated project documentation (`docs/phases/PHASE_02A.md`, `docs/TRANSLATION_INVENTORY.md`, `docs/STATUS.md`, `docs/SESSION_LOG.md`, `docs/VERIFICATION.md`, `docs/DECISIONS.md`).

## 2026-11-07 (Phase 2B Emergency Recovery Incident)
- **Incident**: Phase 2B edit erroneously truncated `templates/index.html` from 12,807 lines down to 2,421 lines, discarding major application views and logic.
- **Recovery Action**:
  - Established isolated backup at `/mnt/data/Companion/recovery/20261107_emergency_recovery/` with full manifest and file hashes.
  - Rolled back `templates/index.html` to exact commit HEAD (`cbea20b436a255e3cd26d952aaf952c003990b65`). Verified byte identity (`git hash-object` matches `31c36dc06f55e58912215c28bd58514ed036b93c`, 12,807 lines).
  - Preserved valid Phase 2A login translation and Phase 2B login-copy corrections in `templates/login.html`.
  - Added strict editing guardrails to `CLAUDE.md` to prevent whole-file replacements, stubs, and unverified large deletions.
  - Corrected project status documents to reflect Phase 2B rollback.
- **Session History Source Note**: Prior session logs and context snapshots from early sessions are reconstructed from conversation archives and git history; any claims regarding intermediate uncommitted states during Phase 2B are explicitly qualified as post-incident recovery records.

## 2026-11-07 (Sora Git Publishing Policy & Checkpoint Push)
- Enforced Sora-only Git publishing policy: `origin` points to `https://github.com/Emii31/Sora.git`, `upstream` points to `https://github.com/kiyotakali/Miru.git` with push disabled.
- Recorded publishing policy in `CLAUDE.md` and `docs/DECISIONS.md`.
- Created policy checkpoint commit and pushed to `origin/main`.

## 2026-11-08 (Phase 2B.2: Identity Settings Panel Translation)
- Translated frontend-owned UI strings in Identity settings panel (field labels, placeholders, save button, flash messages, last-updated timestamp).
- Translated `settingsSaveIdentity` error and success messages ("Failed to save identity settings", "Identity settings saved").
- Changes: 12 insertions, 12 deletions (net 0), 12807 lines preserved.
- Preservation checks: Style blocks and Script blocks byte-for-byte identical (except for authorized UI string updates), DOM IDs, handlers, resources preserved.
- Verification: Syntax validated, git diff --check PASSED.
- Documentation created/updated (`docs/phases/PHASE_02B_2.md`, `docs/STATUS.md`, `docs/VERIFICATION.md`, `docs/SESSION_LOG.md`).
- Pre-edit backup saved at `/mnt/data/Companion/recovery/20261107_emergency_recovery/index_before_phase_2B_2_patch.html`.

## 2026-11-08 (Phase 2B.3: AI Models Settings Panel Translation)
- Translated frontend-owned UI strings in AI Models settings panel (headings, descriptions, field labels, placeholders, configuration status, loading/saving/testing feedback, success/error messages).
- Changes: Contextual patches in `templates/index.html`. 12807 lines preserved.
- Preservation checks: Style and Script blocks byte-identical (except authorized UI string updates).
- Verification: `git diff --check` PASSED.
- Documentation created/updated (`docs/phases/PHASE_02B_3.md`, `docs/STATUS.md`, `docs/VERIFICATION.md`, `docs/SESSION_LOG.md`).
- Pre-edit backup saved at `/mnt/data/Companion/recovery/20261107_emergency_recovery/index_before_phase_2B_3_patch.html`.

## 2026-11-08 (Correction: Phase 2B.3 Records)
- Correction: Appended missing Phase 2B.2 session history accidentally overwritten.
- Updated AI model descriptions to use Sora branding.
- Restored unintentional string changes in `settingsRenderAiriPanel`.

## 2026-11-08 (Test Coverage Recovery Incident)
- **Incident**: Independent review of commit `a3e6503` revealed that `tests/test_owner_ai_config_frontend.py` had missing test functions and assertions covering system invitation codes, account switching, and Windows platform copy.
- **Recovery Action**:
  - Restored all 9 original test functions in `tests/test_owner_ai_config_frontend.py` from commit `c1f8c67`.
  - Updated translated assertion copy expectations to English.
  - Added CLAUDE.md guardrail requiring translation changes to preserve existing test functions and behavioral assertions.
  - Verified full test suite (`tests/test_owner_ai_config_frontend.py`, `tests/test_owner_ai_config.py`, `tests/test_self_profile.py` — 18/18 passed). Saved evidence under `docs/verification/phase_02B_3/test_results.txt`.

## 2026-11-08 (Phase 2B.4: Devices Settings Panel Translation)
- Translated frontend-owned UI strings in Devices settings panel (connection headings, disconnect, connected devices list, online/offline labels, deletion confirmation).
- Changes: Contextual patches in `templates/index.html`. 12807 lines preserved.
- Preservation checks: Style and Script blocks byte-identical (except authorized UI string updates).
- Verification: `git diff --check` PASSED.
- Documentation created/updated (`docs/phases/PHASE_02B_4.md`, `docs/STATUS.md`, `docs/VERIFICATION.md`, `docs/SESSION_LOG.md`).
- Pre-edit backup saved at `/mnt/data/Companion/recovery/20261108_device_backup/index_before_phase_2B_4_patch.html`.

## 2026-11-08 (Phase 2B.5: System Account and Desktop-Preference UI Translation and Repair)
- Translate frontend-owned UI strings in the System panel: invitation code label, loading/copy feedback, local-mode hints, desktop pet shortcuts, screenshot stats notes, account heading, data retention explanation, switch-account confirmation, save button feedback.
- Repaired test assertion in `tests/test_owner_ai_config_frontend.py` to restore strict testing specificity.
- Restored VERIFICATION.md and SESSION_LOG.md history prefix completeness.
- Saved repair evidence under `docs/verification/phase_02B_5_repair/`.

## 2026-11-09 (Phase 2B.5: Final Translation and History Preservation)
- Translated remaining authorized UI strings in System panel: hotkey recording feedback, reset button, save-button feedback, and Miru-to-Sora branding in account descriptions.
- Implemented `scripts/check_history_append_only.py` to enforce documentation prefix integrity for `docs/SESSION_LOG.md` and `docs/VERIFICATION.md`.
- Verified all frontend tests, syntax, and structural constraints.


## 2026-11-09 (Phase 2B.6: Screen Observation and Wallpaper Settings Translation)
- Translated frontend-owned UI strings for screen observation (label, enabled/disabled states, auto-screenshot interval, analyzed screenshots header/loading text) and Android Live2D wallpaper (labels, buttons, status feedback).
- Updated Android capture UI components (_toggleAndroidScreenCapture, _updateAndroidCaptureUI, _updateAndroidWallpaperUI, _syncAllScreenCaptureUI, _updateCaptureHeaderIcon) to English and Sora branding.
- Enforced executable history prefix check via scripts/check_history_append_only.py with starting checkpoint baseline.
- Verified test suite (48 passed across frontend, user-settings, and mobile suites).
- Documentation created/updated (docs/phases/PHASE_02B_6.md, docs/STATUS.md, docs/TRANSLATION_INVENTORY.md, docs/VERIFICATION.md, docs/SESSION_LOG.md).

## 2026-11-09 (Phase 2B.7: Characters List and Detail-Display Translation)
- Translated frontend-owned UI strings in Characters settings panel:
  - Character list heading ("Character List"), upload button label ("Upload Model (.zip)"), loading state ("Loading..."), empty state ("No models found. Add one by uploading or searching in chat."), error state ("Failed to load character list: ").
  - Character-card badge ("In Use").
  - Detail panel navigation ("← Back"), loading state ("Loading character data..."), error state ("Failed to load: ", "Back").
  - Detail panel preview actions ("Use this character", "Change avatar") and Live2D layout controls ("Live2D layout", "Scale", "Save layout").
  - Detail panel form fields and hints (Character Name, Addressing User, Personality, Speech Patterns, Appearance, Backstory, Interests).
  - Character style settings heading and prompt hints (Role Summary, Role Summary (Detailed), Tone Style, Chat Tone, Character Archetype).
  - Advanced settings section and Memory Bank Name field.
  - Detail panel actions ("Save Character Settings", "Delete Character").
- Deferred action behavior, action dialogs (delete confirmation modal), and action handlers/save flash messages as authorized.
- Exact line count of `templates/index.html` preserved at 12807 (32 additions, 32 deletions).
- Ran syntax validation and regression test suite (68 passed).
- Enforced history prefix integrity via `scripts/check_history_append_only.py`.
- Documentation created/updated (`docs/phases/PHASE_02B_7.md`, `docs/STATUS.md`, `docs/TRANSLATION_INVENTORY.md`, `docs/VERIFICATION.md`, `docs/SESSION_LOG.md`).

## 2026-11-09 (Phase 2B.8: Character Action Dialogs and Feedback Translation)
- Translated frontend-owned UI strings for character action dialogs, saving/loading feedback, and action messages within the Characters settings panel:
  - Deletion confirmation modal ("Delete Character", "Delete this character model? Associated soul.md and avatar files will also be deleted. This action cannot be undone.", "Cancel", "Delete").
  - Feedback messages: "Saving...", "Character settings saved", "Save failed...", "Layout saved", "Uploading avatar...", "Avatar updated", "Upload failed...", "soul.md saved", "Renamed", "Rename failed...", "Character switched", "Switch failed...", "Character deleted", "Delete failed...", "Uploading...", "Model uploaded...", "Upload failed...", "Editor content not found".
  - Soul-editor feedback: "Loading...", "Failed to load...".
  - Rename dialog buttons: "OK", "Cancel".
  - Validation messages: "Name cannot be empty".
- Exact line count of `templates/index.html` preserved at 12807 (44 additions, 44 deletions).
- Ran syntax validation and regression test suite (68 passed).
- Enforced history prefix integrity via `scripts/check_history_append_only.py`.
- Documentation created/updated (`docs/phases/PHASE_02B_8.md`, `docs/STATUS.md`, `docs/TRANSLATION_INVENTORY.md`, `docs/VERIFICATION.md`, `docs/SESSION_LOG.md`).

## 2026-11-09 (Phase 2B.9: Chat Controls and Frontend Feedback Translation)
- Translated frontend-owned UI strings for chat controls and feedback mechanisms:
  - Chat composer: placeholder ("Chat with Sora..."), send button ("Send"), voice-input button ("Voice Input").
  - Companion panel: header ("Companion Panel"), description ("Shares chat history with the current ContextLife session"), controls ("Refresh", "Collapse").
  - Feedback: new-message indicator ("New Messages").
- Exact line count of `templates/index.html` preserved at 12807.
- Ran syntax validation and regression test suite (68 passed).
- Enforced history prefix integrity via `scripts/check_history_append_only.py`.
- Documentation created/updated (`docs/phases/PHASE_02B_9.md`, `docs/STATUS.md`, `docs/TRANSLATION_INVENTORY.md`, `docs/VERIFICATION.md`, `docs/SESSION_LOG.md`).

## 2026-11-10 (Phase 2B.9: First-Run Deployment Regression Fix and Test Specificity)
- Repaired first-run deployment regression by restoring the original `miru/server:0.2.0` image identifier in both the `selfImage` input default and the JavaScript fallback in `templates/login.html`.
- Updated `tests/test_first_run_wizard.py` to explicitly verify both image defaults (`miru/server:0.2.0`), restore the scoped `<h1>API Key</h1>` assertion, and restore checks for opening the selected port and checking previous deployment tasks.
- Ran first-run wizard and chat-error tests (`tests/test_first_run_wizard.py` and `tests/test_chat_error_copy.py`) via `PYTHONPATH=. .venv/bin/python -m pytest`, with 7/7 tests passed. Saved evidence under `docs/verification/phase_02B_9_deploy_fix/test_results.txt`.
- Enforced history prefix integrity via `scripts/check_history_append_only.py e40d2dbe88f00d794397d2186c7353995148789b` (PASSED).

## 2026-11-10 (Phase 2B.10: Onboarding Questionnaire Translation)
- Aligned `selfHostHome` defaults in `templates/login.html` and tested image/directory defaults.
- Translated the in-app onboarding questionnaire overlay in `templates/index.html` (welcome heading, subtitle, skip/next/finish buttons, 5 questions, text placeholders, option labels including student, casual, night_owl).
- Preserved all onboarding keys, option values, selection logic, async submission, and persistence behavior.
- Ran onboarding and wizard test suite (20/20 passed). Evidence saved under `docs/verification/phase_02B_10/test_results.txt`.
- Enforced history prefix integrity via `scripts/check_history_append_only.py` (PASSED).

## 2026-11-10 (Phase 2B.11: Memory Browser Overview Translation)
- Translated frontend-owned UI strings in the Memory browser overview (`templates/index.html`):
  - Domain tab labels: Projects, People, Topics, Self (`_DOMAIN_LABELS`).
  - Loading and error states in `navMemoryBrowser`: `"Loading memories..."`, `"Load failed: ..."`.
  - Empty state message in `_buildSlotGroupHtml`: `"No [Domain] memories yet. Chat more with [Miru], and they will organize them automatically."` (preserving character name and neutral pronouns).
  - Archived collapsible heading: `"Archived (n)"`.
  - Slot card metadata and status badge tooltips in `_renderSlotCardHtml`: `"Last active: YYYY-MM-DD"`, `title="Pinned"`, `title="Paused"`, `title="Archived"`, `title="Active"`.
  - Quick-entry index cards in `buildMemoryBrowserHtml`: Core Portrait, Journal (`[Name]'s Journal`), DDLs & Commitments.
- Preserved 12,807-line template, domain keys, item counts, icons, archive visibility rules, caching, routes, and all user data / stored memory content.
- Created `tests/test_memory_browser_dom.js` and `tests/test_memory_browser_dom_render.py`, and ran memory UI test suite (13/13 passed). Evidence saved under `docs/verification/phase_02B_11/test_results.txt` and `EVIDENCE.md`.
- Enforced history prefix integrity via `scripts/check_history_append_only.py 5067d9db4f3d5beb7b8d7785968c133e9461d5f9` (PASSED).

## 2026-11-10 (Phase 2B.12: Memory Detail View and Action Dialogs Translation)
- Translated frontend-owned UI strings in the Memory detail view and action handlers/dialogs (`templates/index.html`):
  - Detail view loading/error states (`"Loading..."`, `"Load failed: ..."`, `"Memory does not exist"`).
  - Status labels (`"Active"`, `"Paused"`, `"Archived"`), metadata fields (`"Summary:"`, `"Aliases:"`, `"Created:"`, `"Last active:"`, `"Related DDL"`, `"Content"`, `"Content is empty"`), and delete action button (`🗑 Delete`).
  - Slot action dialogs and feedback messages:
    - Archive confirmation & error (`"Archive this memory? It will not appear in the main memory view."`, `"Archive failed (...)"`).
    - Unarchive and pin error messages (`"Unarchive failed (...)"`, `"Pin operation failed (...)"`).
    - Delete confirmation & error (`"Are you sure you want to delete this memory? This action cannot be undone, and the main file will also be deleted."`, `"Delete failed (...)"`, `"Server rejected"`).
    - Edit modal (`"Edit memory"`, Title, Icon, Summary, Aliases, Cancel, Save, Save failed).
    - Merge modal (`"Merge into which memory?"`, merge description, candidate check `"No other memories available to merge in this domain"`, Confirm Merge, progress indicator `"LLM is merging content, please wait..."`, Merge failed).
  - Updated overview empty-state fallback character name to `"Sora"` (`(window.CHARACTER && CHARACTER.name) || 'Sora'`).
- Preserved 12,807-line template, internal slot keys, routes, request methods, payload keys, cache invalidation, and navigation.
- Updated `tests/test_memory_browser_dom.js` and `tests/test_memory_browser_dom_render.py`, and ran memory UI test suite (13/13 passed). Evidence saved under `docs/verification/phase_02B_12/test_results.txt` and `EVIDENCE.md`.
- Enforced history prefix integrity via `scripts/check_history_append_only.py 5343bb58e959662fb8944c91a9928513b4535783` (PASSED).

## 2026-11-10 (Phase 2B.13: Core Portrait and Journal Views Translation)
- Translated frontend-owned UI strings in Core Portrait and Journal views (`templates/index.html`):
  - Core Portrait (`navCoreMemory`, `_renderCoreMemoryHtml`, `_renderCoreMemoryBlock`): loading/error states, title ("Core Portrait"), status ("Always injected into main chat and AttentionEngine"), block titles ("My understanding of you", "My relationship with you"), empty state ("No content yet.").
  - Journal views (`buildJournalListHtml`, `buildJournalBookHtml`, `showMiruJournalList`, `viewJournalDetail`, `_buildJournalGalleryHtml_LEGACY`, `_shareJournalAsPng`): list title/subtitle, today pending status & wait messages, legacy hints & badges, book highlights ("Memories of the Day"), narrative fallback ("(She remembers you were not around.)"), stats strip ("First active", "Last active", "N messages"), prev/next buttons ("← Previous day", "Next day →"), share button ("Share"), and error/loading toast messages.
- Preserved 12,807-line template, stored entries, narratives, Markdown, dates, counts, character names, routes, cache behavior, back targets, and escaping.
- Updated `tests/test_memory_browser_dom.js` and `tests/test_memory_browser_dom_render.py`, and ran test suites (`tests/test_memory_browser_dom_render.py`, `tests/test_journal_navigation_frontend.py`, `tests/test_mobile_notification_memory_ui.py`) — all passed successfully. Evidence saved under `docs/verification/phase_02B_13/test_results.txt` and `EVIDENCE.md`.
- Enforced history prefix integrity via `scripts/check_history_append_only.py a0e31fd458c00e765524281e872e04c8f83043ae` (PASSED).

## 2026-11-10 (Phase 2B.14: Commitments Overview and Journal Localization & Finalization)
- Finalized Journal date formatting (`_journalFormatDate` returning English month and weekday), corrected the March date example in `_journalFormatDate` to say "Mar 2026", and set configured fallback character name to `"Sora"` with HTML escaping in Journal list and book views (`templates/index.html`).
- Translated Commitments (DDL) tracker overview and list (`navDDLTracker`, `_loadDDLView`, `_buildDDLViewHTML`, `_buildDDLListView`, `_ddlItemCard`): headings ("Commitments"), view toggle buttons ("List", "Calendar"), add action button ("+ New"), stats badges ("Active", "Overdue", "Completed"), add form placeholders & buttons, urgency group labels ("Overdue", "Due Today", "Within 3 Days", "In Progress", "No Deadline"), completed items section & metadata ("Due", "Added"), and action button titles ("Mark complete", "Delete").
- Preserved internal identifiers, status values, routes, payloads, caching, date logic, saved user content, and 12,807-line template exact.
- Updated test suite evidence under `docs/verification/phase_02B_14/test_results.txt`.
- Enforced history prefix integrity via `scripts/check_history_append_only.py c6fa892af815d5fcda928d6af776eb791e192732` (PASSED).
