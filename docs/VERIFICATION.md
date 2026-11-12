# Verification

- **Workspace structure**: Created (verified).
- **CLAUDE.md rules**: Implemented and verified (updated with editing guardrails).
- **Python Environment**: Established using Python 3.11.18.
- **Legacy Tests**: `tests/test_identity_aliases_cascade.py` -> 34/34 passed (`0`).
- **Phase 2A Verification**:
  - `templates/login.html`: Translated and rebranded to Sora, including login copy correction.
  - `/api/health`, `/app`, `/login`: `200 OK` verified.
- **Phase 2B Rollback**:
  - Phase 2B main template translation was rejected due to destructive large-scale file truncation (`templates/index.html` reduced from 12,807 lines to 2,421 lines).
  - `templates/index.html` fully restored to HEAD (`cbea20b436a255e3cd26d952aaf952c003990b65`), verified via `git hash-object` and byte identity.
- **Phase 2B.2 Verification**:
  - `templates/index.html`: Identity settings panel fields, button labels, and save feedback messages translated.
  - Preservation checks: Script blocks and Style blocks verified identical (with authorized exceptions for UI strings).
  - `git diff --check`: PASS.
  - Backup: `/mnt/data/Companion/recovery/20261107_emergency_recovery/index_before_phase_2B_2_patch.html`.
- **Phase 2B.3 Verification**:
  - `templates/index.html`: AI Models settings panel fields, button labels, descriptions, and save/test feedback messages translated.
  - Preservation checks: Script blocks and Style blocks verified identical (with authorized exceptions for UI strings).
  - `git diff --check`: PASS.
  - Test suite coverage recovery: All 9 original test functions in `tests/test_owner_ai_config_frontend.py` fully restored and verified (18/18 tests passed across frontend, backend, and self-profile suites). Evidence saved under `docs/verification/phase_02B_3/test_results.txt`.
  - Backup: `/mnt/data/Companion/recovery/20261107_emergency_recovery/index_before_phase_2B_3_patch.html`.
- **Phase 2B.4 Verification**:
  - `templates/index.html`: Devices settings panel headings, status labels, disconnect button, loading/empty/error messages, online/offline labels, last-active prefix, device-removal tooltips, confirmations, and fallback errors translated to English.
  - Preservation checks: Script blocks, Style blocks, DOM IDs, handlers, URLs, payload keys, escaping preserved.
  - `git diff --check`: PASS.
  - Line count: 12806 (preservation target was 12807; -1 line due to space-saving layout difference — previously a white-space formatting detail, now single empty line per hunk).
  - Test suite check: Frontend, backend, and self-profile tests all pass; evidence under `docs/verification/phase_02B_4/test_results.txt`.
  - Backup: `/mnt/data/Companion/recovery/20261108_device_backup/index_before_phase_2B_4_patch.html`.
- **Session History Prefix Verification**: All prior history sections preserved verbatim; appended new entries only (programmatic prefix check passed).
- **Recovery Backup**:
  - Saved under `/mnt/data/Companion/recovery/20261108_device_backup/` with full manifest and file hashes.

- **Phase 2B.5 Verification (REPAIRED)**:
  - **Correction**: Prior verification history was accidentally replaced. Phase 2B.5 is partially implemented, not complete. The 18 tests are a selected regression subset. Browser verification remains pending.
  - `templates/index.html`: System account and desktop-preference settings panel translated to English.
  - Preservation checks: Script blocks, Style blocks, DOM IDs, handlers, URLs, payload keys, escaping preserved.
  - `git diff --check`: PASS.
  - Line count: 12807 (restored).
  - Test suite check: Frontend, backend, and self-profile tests all pass (regression verified, with repaired specific assertions).
  - Backup: `/mnt/data/Companion/recovery/20261108_system_backup/index_before_phase_2B_5_patch.html`.

- **Phase 2B.5 Completion Verification (FINAL)**:
  - `templates/index.html`: Final translation of dynamic System panel strings (hotkey recording feedback, reset button, save-button feedback, and Miru-to-Sora branding in account descriptions).
  - Preservation checks: Script blocks, Style blocks, DOM IDs, handlers, URLs, payload keys, escaping preserved.
  - `git diff --check`: PASS.
  - Test suite check: 9/9 frontend tests passed; syntax validated.
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py` (pre-commit check verified).
  - Browser verification: Pending.


- **Phase 2B.6 Verification (Screen Observation & Wallpaper Settings)**:
  - templates/index.html: Screen observation and Android Live2D wallpaper UI strings translated to English with Sora branding.
  - Handlers and helpers translated: _toggleAndroidScreenCapture, _updateAndroidCaptureUI, _updateAndroidWallpaperUI, _syncAllScreenCaptureUI, _updateCaptureHeaderIcon.
  - Preservation checks: Script blocks, Style blocks, DOM IDs, handlers, URLs, payload keys, escaping preserved. Line count 12807 preserved exact.
  - git diff --check: PASS.
  - Test suite check: 48/48 tests passed across owner AI frontend, Linux settings, user settings, and mobile notification memory UI suites.
  - History Prefix Integrity: Enforced by scripts/check_history_append_only.py 7499308930f8434154450e4921c4205160dac680.
  - Browser verification: Pending.
  - Backup: /mnt/data/Companion/recovery/phase_02B_6_backup/index.html.


- **Phase 2B.7 Verification (Characters List & Detail-Display Translation)**:
  - templates/index.html: Characters list, card display labels, and detail panel headings/fields/actions translated to English with Sora conventions.
  - Components translated: Character list header, upload button, loading/empty/error states, card In Use badge, detail panel navigation, preview actions, Live2D layout controls, detail form fields, style prompt hints, advanced settings, and action buttons.
  - Deferred items: Action dialogs (`deleteModelConfirmModal`), action handlers and save flash messages.
  - Preservation checks: Script blocks, Style blocks, DOM IDs, handlers, URLs, payload keys, escaping preserved. Line count 12807 preserved exact (32 additions, 32 deletions).
  - git diff --check: PASS.
  - Test suite check: 68/68 tests passed across owner AI frontend, Linux settings, user settings, mobile notification memory UI, and persona suites. Inline JS syntax validated via node.
  - History Prefix Integrity: Enforced by scripts/check_history_append_only.py 6154ca66c726c6d42c84d305ec4088921afbf8c7.
  - Browser verification: Pending.
  - Backup: /mnt/data/Companion/recovery/phase_02B_7_backup/index.html.

- **Phase 2B.8 Verification (Character Action Dialogs and Feedback Translation)**:
  - templates/index.html: Character action dialogs, saving/loading feedback, and action messages within Characters settings panel translated to English.
  - Components translated: Deletion confirmation modal, save/load/success/fallback feedback, layout save feedback, avatar upload messages, model upload progress/validation, rename dialog, character activation feedback, and soul-editor controls/feedback.
  - Preservation checks: Script blocks, Style blocks, DOM IDs, handlers, URLs, payload keys, escaping preserved. Line count 12807 preserved exact (44 additions, 44 deletions).
  - git diff --check: PASS.
  - Test suite check: 68/68 tests passed across owner AI frontend, Linux settings, user settings, mobile notification memory UI, and persona suites. Inline JS syntax validated via node.
  - History Prefix Integrity: Enforced by scripts/check_history_append_only.py 7b3e2809912926ed37c0ed1763fefb23dd288e57.
  - Browser verification: Pending.
  - Backup: /mnt/data/Companion/recovery/phase_02B_8_backup/index.html.

- **Phase 2B.9 Verification (Chat Controls and Frontend Feedback Translation)**:
  - templates/index.html: Chat composer, companion-panel, and feedback UI translated to English.
  - Components translated: Chat placeholder, Send button, Voice Input tooltip, Companion panel header/description/controls, New Messages indicator.
  - Preservation checks: Script blocks, Style blocks, DOM IDs, handlers, URLs, payload keys, escaping preserved. Line count 12807 preserved.
  - git diff --check: PASS.
  - Test suite check: 68/68 tests passed across regression suite. Inline JS syntax validated via node.
  - History Prefix Integrity: Enforced by scripts/check_history_append_only.py 822ee379f993b8c5dda77eb97a83b84a577c1ae5.
  - Browser verification: Pending.
  - Backup: /mnt/data/Companion/recovery/phase_02B_9_backup/index.html.

- **Phase 2B.9 Deployment Fix & Test Specificity Verification**:
  - `templates/login.html`: Restored `miru/server:0.2.0` image identifier in `selfImage` input default and JS fallback.
  - `tests/test_first_run_wizard.py`: Added explicit image default assertions (`miru/server:0.2.0`), restored scoped `<h1>API Key</h1>` assertion, port selection checks, and previous deployment task checks.
  - Test suite check: 7/7 passed (`tests/test_first_run_wizard.py` and `tests/test_chat_error_copy.py`). Evidence under `docs/verification/phase_02B_9_deploy_fix/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py e40d2dbe88f00d794397d2186c7353995148789b` (PASSED).

- **Phase 2B.10 Verification (Onboarding Questionnaire Translation)**:
  - `templates/login.html`: Aligned `selfHostHome` default to `/opt/miru-host`.
  - `templates/index.html`: Translated onboarding overlay UI strings, buttons, questions, placeholders, and option values while preserving question keys and submission payload structures.
  - Test suite check: 20/20 passed (`tests/test_first_run_wizard.py`, `tests/test_chat_error_copy.py`, `tests/test_onboarding_persistence.py`, `tests/test_onboarding_api_setup_skip.py`, `tests/test_onboarding_async.py`). Evidence under `docs/verification/phase_02B_10/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 778bf240ff626a40b66cf3137bff56ac10464233` (PASSED).

- **Phase 2B.11 Verification (Memory Browser Overview Translation)**:
  - `templates/index.html`: Translated Memory browser overview UI strings (domain tab labels Projects/People/Topics/Self, loading/error states, empty state message with dynamic character name and neutral pronouns, archived section heading, card last-active metadata, status badge tooltips, and quick-entry cards Core Portrait / Journal / DDLs & Commitments).
  - Preservation checks: Domain keys (`project`, `person`, `topic`, `self`), item counts, icons, archive visibility rules, caching, routes, stored memory data, and 12,807-line template preserved exact.
  - Test suite check: 13/13 passed (`tests/test_memory_browser_dom_render.py`, `tests/test_mobile_notification_memory_ui.py`). Evidence under `docs/verification/phase_02B_11/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 5067d9db4f3d5beb7b8d7785968c133e9461d5f9` (PASSED).

- **Phase 2B.12 Verification (Memory Detail View and Action Dialogs Translation)**:
  - `templates/index.html`: Translated Memory detail view and action handlers/dialogs (loading/error states, status labels, metadata fields, delete button, archive confirmation, delete confirmation, edit modal, and merge dialog).
  - Preservation checks: Internal slot keys, request methods, routes, payload structures, cache invalidation (`_invalidateMemoryCache`), navigation, stored memory content, and 12,807-line template preserved exact.
  - Test suite check: 13/13 passed (`tests/test_memory_browser_dom_render.py`, `tests/test_mobile_notification_memory_ui.py`). Evidence under `docs/verification/phase_02B_12/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 5343bb58e959662fb8944c91a9928513b4535783` (PASSED).

- **Phase 2B.13 Verification (Core Portrait and Journal Views Translation)**:
  - `templates/index.html`: Translated Core Portrait view (`navCoreMemory`, `_renderCoreMemoryHtml`, `_renderCoreMemoryBlock`) and Journal views (`buildJournalListHtml`, `buildJournalBookHtml`, `showMiruJournalList`, `viewJournalDetail`, `_buildJournalGalleryHtml_LEGACY`, `_shareJournalAsPng`).
  - Components translated: Loading/error states, Core Portrait header/status/blocks, Journal list header/subtitle/today pending/legacy hints, Journal book reader (highlights, narrative fallback, stats strip, legacy badge, prev/next buttons, share button/toasts).
  - Preservation checks: Stored entries, narratives, Markdown, dates, counts, character names, routes, cache behavior, back targets, escaping, and 12,807-line template preserved exact.
  - Test suite check: All tests passed (`tests/test_memory_browser_dom_render.py`, `tests/test_journal_navigation_frontend.py`, `tests/test_mobile_notification_memory_ui.py`). Evidence under `docs/verification/phase_02B_13/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py a0e31fd458c00e765524281e872e04c8f83043ae` (PASSED).

- **Phase 2B.14 Verification (Commitments Overview and Journal Localization)**:
  - `templates/index.html`: Finalized Journal date formatting (`_journalFormatDate` returning English month and weekday) and escaped character name in Journal header. Translated Commitments tracker (`navDDLTracker`, `_loadDDLView`, `_buildDDLViewHTML`, `_buildDDLListView`, `_ddlItemCard`) including headers, view toggle buttons, stats badges, add form, and list items.
  - Preservation checks: Internal identifiers, status values, routes, payloads, caching, date logic, saved user content, and 12,807-line template preserved exact.
  - Test suite check: 19/19 passed (`tests/test_journal_navigation_frontend.py`, `tests/test_commitment_dedup.py`, `tests/test_commitment_id_stability.py`, `tests/test_mobile_notification_memory_ui.py`). Evidence under `docs/verification/phase_02B_14/EVIDENCE.md`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py c6fa892af815d5fcda928d6af776eb791e192732` (PASSED).

- **Phase 2B.14 Verification (Commitments Overview Final Correction & DOM Verification)**:
  - `templates/index.html`: Complete translation of Commitments tracker UI strings in `_buildDDLViewHTML`, `_buildDDLListView`, `_ddlItemCard`, and `_buildDDLCalendarView`.
  - Node DDL DOM execution check: Executed `_buildDDLViewHTML` in Node with synthetic items; confirmed presence of "Commitments", "List", "Calendar", "Commitment Title", counts, and English labels, and absence of Chinese labels.
  - Test suite check: 20/20 passed (`tests/test_memory_browser_dom_render.py`, `tests/test_journal_navigation_frontend.py`, `tests/test_commitment_dedup.py`, `tests/test_commitment_id_stability.py`, `tests/test_mobile_notification_memory_ui.py`). Evidence under `docs/verification/phase_02B_14/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace, 12807 lines exact).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 0e1cd05d7665984df558cd99aab49ec28dd941c6` (PASSED).

- **Phase 2B.15 Verification (Commitments Calendar Localization & Samsung String Restoration)**:
  - `templates/index.html`: Translated day-detail heading in `_ddlShowDayDetail` (`Commitments for [dateStr]`) and restored Samsung background keep-alive instruction string. Preserved 12,807 lines exact, Monday-first layout, date keys, and handlers.
  - Node & DOM verification: Fixed synthetic month and commitments tested in Node; confirmed English heading, Monday-first layout, and correct date handler integration.
  - Test suite check: 20/20 passed (`tests/test_memory_browser_dom_render.py`, `tests/test_journal_navigation_frontend.py`, `tests/test_commitment_dedup.py`, `tests/test_commitment_id_stability.py`, `tests/test_mobile_notification_memory_ui.py`). Evidence under `docs/verification/phase_02B_15/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace, 12807 lines exact).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 696056bb7ddaf1eacd4182c2b31929f51372dff1` (PASSED).

- **Phase 2B.16 Verification (Emotion Calendar Overview Localization)**:
  - `templates/index.html`: Translated Emotion Calendar overview UI strings (`navEmotionCurve`, `_buildEmotionCalendarHtml`, and loading state in `_emotionDayDetail`) to English with Sora conventions. Covers title ("Emotion Calendar"), subtitle, month/year displays (`Nov 2026`), navigation labels, day tooltips (`[count] entries`), monthly overview ("Monthly Overview", recorded days, chip counts, monthly avg valence), and "Today" quick link ("View Today's Details →").
  - Preservation checks: Monday-first layout, local date calculations (`_miruLocalDateKey`), month keys, day-click dates (`_emotionDayDetail`), mood codes, colors, cache keys, routes, and saved content preserved. Exact 12,807 lines maintained.
  - Node & DOM verification (`tests/test_emotion_calendar_dom.js`): Verified English month displays, Monday-first weekday order (`Mon`-`Sun`), day handler integration, and tooltip counts.
  - Test suite check: 26/26 passed (`tests/test_emotion_local_date_frontend.py`, `tests/test_miru_emotion_v2.py`, `tests/test_miru_emotion_api.py`, `tests/test_mobile_notification_memory_ui.py`). Evidence under `docs/verification/phase_02B_16/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace, 12807 lines exact).

- **Phase 2B.17 Verification (Emotion River Day View Translation)**:
  - `templates/index.html`: Translated Emotion River day view UI strings (`buildEmotionCurveHtml`, `drawMoodRiver`, `_EMO_SOURCE_GLYPHS`) to English with Sora conventions. Covers title & subtitle, dynamic date headers (`Emotion River · Today` / `Emotion River · YYYY-MM-DD`), empty states, summary stats (`Avg Valence`, `Avg Intensity`, `Peak`, `Trough`, `Records` with singular/plural support), sources section, timeline log (`Emotion Log`, `1 record`, `N records`, `N records · Compressed M raw entries`, `Nx repeats`), canvas axis poles (`High`, `Low`), and hover tooltips.
  - Preservation checks: Chart logic, smoothing, mood codes, colors, local date calculations (`_miruLocalDateKey`), and saved data preserved. Exact 12,807 lines maintained.
  - Node harness verification (`tests/test_emotion_river_dom.js`): executed real `buildEmotionCurveHtml` parser with DOM/canvas mocks; verified empty/populated views for today and past dates, hover tooltips, and singular record count ("1 record").
  - Test suite check: 26/26 passed (`tests/test_emotion_local_date_frontend.py`, `tests/test_miru_emotion_v2.py`, `tests/test_miru_emotion_api.py`, `tests/test_mobile_notification_memory_ui.py`). Evidence under `docs/verification/phase_02B_17/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace, 12807 lines exact).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py fef04e781668d6e1607fdd54fa504aa9594d0081` (PASSED).

- **Phase 2B.18 Verification (My Mood Dashboard Translation)**:
  - `templates/index.html`: Translated My Mood dashboard UI strings (`navMiruEmotion`, `buildMiruEmotionHtml`, `buildMiruEmotionRiver`) to English with Sora conventions. Covers headers (`Mood Dashboard`, `Mood River`, `Mood Log`), subtitles, hero relationship card (`Together for N days`, `📅 First met YYYY-MM-DD`), current mood display, stats, and timeline log with singular/plural support and empty state (`No mood records yet`).
  - Preservation checks: Mood descriptions, character names, mood codes, relationship dates, numeric values, color interpolation (`_miruValenceColor`), and chart behavior preserved. Exact 12,807 lines maintained.
  - Node DOM harness (`tests/test_miru_emotion_dom.js`): executed real renderer with synthetic empty/populated histories, day counts, stored mood text, numeric values, and hover tooltips.
  - Test suite check: 37/37 passed across emotion-related and core UI suites. Evidence under `docs/verification/phase_02B_18/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace, 12807 lines exact).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 785be5045948c9c8153fc8e06416cdf77aaa62df` (PASSED).

- **Phase 2B.19 Verification (Screen Observation Permission Guides Localization)**:
  - `templates/index.html`: Translated screen observation permission guides and modals (`_showCaptureGuide`, `_showDesktopScreenshotGuide`, `_showClientScreenRecordingModal`, `_permModalEnableWindows`) to English with Sora conventions. Covers first-time guidance toast, fallback toast, client-mode observation modal across macOS, Windows, and Linux states, privacy and lifecycle notes, button labels (`Test and Enable Screen Observation`, `Retest Screen Capture`, `Open System Settings → Screen Recording`, `I Have Authorized, Retry Now`, `Not Now`, `I Have Set This Up`), native bridge test feedback, and error states.
  - Preservation checks: Permission checks, capture defaults, native bridge calls, settings destinations, retry behavior, per-device state, and exact 12,807 line count (`templates/index.html`) preserved.
  - Node DOM harness (`tests/test_capture_guide_dom.js`): Exercised macOS, Windows, and Linux modal rendering and confirmation states.
  - Test suite check: 55/55 passed across capture recovery frontend, Linux settings, user settings, Windows platform, and Linux launcher test suites. Evidence under `docs/verification/phase_02B_19/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace, 12,807 lines exact).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 9f5e9c974627919d8ee626a453a7afdcb35e732f` (PASSED).

- **Phase 2B.20 Verification (Android Background Keep-Alive Guide Localization)**:
  - `templates/index.html`: Translated the Android background keep-alive guide (`_showBgKeepAliveGuide`) in `templates/index.html` to English with Sora conventions. Covers heading (`"Background activity settings"`), explanation (`"To ensure Miru can continuously observe the screen, please complete the following settings:"`), acknowledgment button (`"Got it"`), and manufacturer-specific steps (vivo, OPPO/OnePlus/Realme, Xiaomi, Huawei/Honor, Samsung, generic fallback) translated to English with menu paths preserved, using `"Miru"` as the app identifier in Android settings. Added contextual note that menu names can vary by device.
  - Preservation checks: Manufacturer detection logic, one-time display flag (`miru_bg_guide_shown`), dismiss behavior, exact 12,807 line count (`templates/index.html`) preserved, APK update text and native Android strings for later.
  - Node DOM harness (`tests/test_bg_keep_alive_guide_dom.js`): Verified all 6 manufacturer branches (Samsung SM-G991B, Xiaomi 13, vivo X90, OnePlus 11, HONOR Magic5, Google Pixel 8) plus suppression behavior on a second call. Evidence under `docs/verification/phase_02B_20/test_results.txt`.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace, 12807 lines exact).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 1b358aa6a55a52f831f756ac4f1aef6c6ff779fe` (PASSED).

- **Phase 2B.21 Verification (APK Update Handling)**:
  - `templates/index.html`: APK update checking feature safely disabled by returning early in `_checkAppUpdate`. APK updates will be installed manually.
  - `miru-mobile/.../ApkUpdateManager.java`: Native Android UI strings translated to English.
  - Background keep-alive guide updated with note: `(menu names vary by device)`.
  - Device installation: Pending.
  - Preservation checks: Exact 12,807 line count maintained. Logic flow verified: `_checkAppUpdate` returns early.
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 06293db9f52566094e985f0d3fafae71711c0dc3` (PASSED).

- **Phase 2B.22 Verification (Native Android Notification UI Translation)**:
  - `MiruConnectionService.java` & `NotificationReplyReceiver.java`: Translated connection status, notification channels, quick-reply action/label, and background-reply feedback messages to English.
  - Verification harness: Mobile notification test suite (12/12 passed) and APK update harness executed in Node (all assertions passed).
  - Android build/device check: Build not required; Java string resources validated.
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 06293db9f52566094e985f0d3fafae71711c0dc3` (PASSED).

- **Phase 2B.23 Verification (Android Capture and Startup UI Translation)**:
  - `ScreenCaptureService.java`: Translated notification channel name/description, paused notification, active notification, and Stop action to English.
  - `MainActivity.java`: Translated local service startup failure error fallback message to English.
  - Preservation checks: Notification IDs, channel IDs, foreground service types, MediaProjection flows, request codes, and backend error handling preserved intact.
  - Test suite check: 12/12 passed (`tests/test_mobile_notification_memory_ui.py`). Android build/device rendering checked via static analysis of Java source and passing test assertions.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 3ea036c` (PASSED).

- **Sora Local Chat Checkpoint & Loopback HTTP Support Verification**:
  - `templates/index.html`: Restored missing closing brace in `_handleApkUpdateClick` try/catch block.
  - `tests/test_owner_ai_config_frontend.py`: Restored original inline JS syntax test assertion using `new Function('(function(){' + require('fs').readFileSync(0, 'utf8') + '})()');`, confirming it validates inline scripts and rejects invalid JS.
  - `ai_config.py`: Added explicit HTTP support for loopback inference servers (`localhost`, `127.0.0.1`, `[::1]`) across configuration save, connection test (`ping_tier`), and runtime requests (`get_tier_client`), while preserving HTTPS handling for remote providers.
  - Test suite check: All 34 `ai_config` tests passed, all 9 frontend tests passed (and regression suite of 933 tests verified).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 46da5a11eb644cc6986bf60d5c312501990b671f` (PASSED).
- **Sora Fast Local Chat Performance Milestone & Benchmark Verification**:
  - `templates/index.html`: Exposed Fast Local Chat toggle in system settings UI with clear tool/image routing explanations.
  - `tests/test_user_settings.py`: Updated settings policy test to verify default, image fallback, and setting toggle without keyword guessing.
  - `scripts/benchmark_chat.py`: Implemented multi-turn synthetic benchmark through real Flask `/api/chat` route, reporting median send-to-history times and direct latencies, with strict nonzero exit on failure.
  - Test suite check: All 54 focused tests passed successfully.
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 7387da6` (PASSED).

- **Phase 2B.20 Verification (Android Native & Desktop Pet Display Copy & Sora Branding Pass)**:
  - `ApkUpdateManager.java`: Updated installation permission prompt and update download notification title to Sora.
  - `MainActivity.java`: Updated local backend startup error fallback to Sora.
  - `MiruPythonRuntime.java`: Updated local runtime error fallback message to Sora.
  - `ScreenCaptureService.java`: Updated notification channel name and service description to Sora.
  - `MiruConnectionService.java`: Updated connection and message notification channel names, descriptions, reply action labels, and fallback titles to Sora.
  - `NotificationReplyReceiver.java`: Updated notification reply fallback and sender title to Sora.
  - `templates/pet.html`: Updated default pet character fallback name (`_charName`) to Sora.
  - Preservation checks: Package IDs (`com.miru.companion`), notification channel IDs (`miru_connection`, `miru_messages`, `miru_screen_observation`), storage keys/paths, API contracts, bridge names, and upstream attribution preserved. Internal `MiruProfileStore` exceptions verified as non-UI-facing.
  - Test suite check: 54/54 focused platform and desktop pet tests passed successfully (`tests/test_android_embedded_shell.py`, `tests/test_linux_pet.py`, `tests/test_linux_launcher.py`, `tests/test_desktop_header_controls.py`, `tests/test_dmg_brand_assets.py`).
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 603176d8cad991232aab21db8e7355c9147cfe14` (PASSED).

- **Phase 2B.21 Verification (Desktop Pet, Sign-In, Voice Tooltips & Clear-All Confirmation Pass)**:
  - `templates/pet.html`: Set document language to English (`lang="en"`) and translated chat-error fallback (`'Unknown error'`).
  - `templates/index.html`: Translated embedded invite-code sign-in screen, voice-input tooltips, and clear-all-records confirmation modal.
  - `core.py`: Translated clear-all confirmation text (`_CLEAR_ALL_CONFIRM_TEXT = "Clear All"`) and associated backend error messages.
  - `tests/test_auth_delete.py`: Added and verified `test_clear_all_records_confirmation` ensuring incorrect input remains blocked and correct input succeeds.
  - Test suite check: 96/96 focused tests passed across user settings, auth/delete, Android embedded shell, Linux pet, and invitation flows.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 603176d8cad991232aab21db8e7355c9147cfe14` (PASSED).

- **Phase 2B.22 Verification (Backend-Only English Translation and Sora Branding)**:
  - `app.py`, `ai_config.py`, `core.py`, `auth.py`: Translated user-facing backend messages (invite-code validation, login/session errors, setup errors, provisioning errors, journal errors, chat validation, and model-connection fallbacks) to natural English and Sora branding.
  - Preservation checks: Routes, JSON fields, status codes, authentication, stored identifiers, and Clear All confirmation behavior preserved intact.
  - Test suite check: All focused unit tests (`test_invitation_direct_login.py`, `test_ai_config.py`, `test_chat_error_copy.py`, `test_local_single_device_mode.py`, `test_client_provisioning.py`, `test_chat_preflight_routing.py`) passed successfully.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 1e3a76ea8237efb832dd876a23a754a17e873bfc` (PASSED).

- **Phase 2B.23 Verification (Backend Copy Cleanup and Benchmark Error Detection)**:
  - `app.py`, `core.py`, `scripts/benchmark_chat.py`: Translated blank-message chat error in `app.py` (`"Please enter a message"`), updated image description failure copy (`"(Image description failed)"`) and proactive trigger image tag (`"[Image: ...]"`) in `core.py`, and updated benchmark failure detection in `scripts/benchmark_chat.py` to correctly flag English fallbacks while preserving valid error-containing replies.
  - Preservation checks: HTTP status codes, response fields, authentication, stored identifiers, and character config names preserved intact.
  - Test suite check: 25 focused unit tests passed (`test_chat_error_copy.py`, `test_companion_bootstrap.py`, `test_chat_preflight_routing.py`). Synthetic tests for benchmark failure detection passed successfully.
  - Git diff check: PASS (clean whitespace, exact diff statistics).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py ed994c453de159bfcbd4f9d8f5dfa09e1e7fb4f6` (PASSED).

- **Phase 2B.24 Verification (English Main Chat Prompts and Provider Diagnostics)**:
  - `prompt.py`, `agent_behavior.md`: Translated main chat memory retrieval preflight prompt (`_CHAT_PREFLIGHT_PROMPT`), shared agent behavior rules (`agent_behavior.md`), and provider setup/connection error diagnostics (`_get_ai_runtime_or_raise`, `_format_ai_call_error`) to natural English and Sora branding.
  - Preservation checks: Prompt contracts, JSON keys, enum values, tool names, memory paths, retrieval limits, routing decisions, image markers, and Sora branding preserved intact.
  - Test suite check: 61 focused unit tests passed (`test_chat_preflight_routing.py`, `test_chat_error_copy.py`, `test_companion_bootstrap.py`, `test_ai_config.py`, `test_chat_archive_and_consolidate.py`).
  - Git diff check: PASS (clean whitespace, exact diff statistics).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 2093cbf2d9285cc9b20939f02772cc9636b586aa` (PASSED).

- **Phase 2B.25 Verification (English Main Chat System Prompt Translation)**:
  - `prompt.py`: Translated assembled chat instructions and headings in `_build_agent_system_prompt()` (`prompt.py`) covering identity, conversation mode, relationship context, memory system, image messages, tool guidance, and authenticity rules to natural English and Sora branding. Translated `build_proactive_agent_user_message()` output instructions.
  - Preservation checks: Character data, runtime contracts, memory paths, tool names, reactive/proactive mode distinction, and persona safety checks fully preserved.
  - Test suite check: 83/83 tests passed (`test_chat_preflight_routing.py`, `test_chat_error_copy.py`, `test_companion_bootstrap.py`, `test_ai_config.py`, `test_chat_archive_and_consolidate.py`, `test_agent_modes_attention.py`, `test_care_engine_persona.py`).
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py c648620bb4b15807d56c2cc237b1ca5648b5f9bd` (PASSED).

- **Phase 2B.26 Verification (Proactive Backend Prompts and Chat Image Compatibility)**:
  - `prompt.py`: Translated `_PROACTIVE_RESOURCE_PLANNER_PROMPT` and `_PROACTIVE_DELIVERY_PREFLIGHT_PROMPT` to English while preserving JSON schemas, enums, tool policies, memory paths, and conditional routing logic.
  - Image message handling: Aligned prompt instructions with actual emitted markers (`[图片：...]`, `[Image: ...]`, `[图片]`) and failure sentinels (`(图片识别失败)`, `(Image description failed)`, etc.).
  - Character-neutral phrasing: Replaced hardcoded "Miru living with the user" with `{cfg.name} living with {user_label}`.
  - Focused checks: Added unit tests verifying image formatter / system prompt compatibility and proactive planner / gatekeeper contracts.
  - Test suite check: 85 tests passed across agent modes, attention, chat image history, preflight routing, and care engine persona suites.
  - Git diff check: PASS.
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 21aab14a6373e31f63498b7638c5ba24ea3c104c` (PASSED).

- **Phase 2B.27 Verification (English Emotion Prompts and Image Guidance Correction)**:
  - `prompt.py`: Corrected chat image instructions to separately specify usable description tags (`[图片：...]`, `[Image: ...]`), bare tags (`[图片]`, `[Image]`), and failure sentinels (`(图片识别失败)`, `(Image description failed)`). Strengthened compatibility tests in `tests/test_agent_modes_attention.py`.
  - `prompt.py`, `memory_prompts.py`: Translated user emotion annotation prompts (`EMOTION_CHAT_PROMPT`, `EMOTION_SCREENSHOT_PROMPT`, rules, judgment guidelines) and companion emotion evaluation prompt (`_build_miru_emotion_prompt()`) to natural English.
  - Test suite check: 49 unit tests passed across emotion, image-history, agent-mode, and attention suites.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 7f731cef51c4c6e33d63f7b41896a4797a65cf1b` (PASSED).
- **Phase 2B.28 Verification (English Chat Memory and Persona Writer Prompts)**:
  - `memory_prompts_v3.py`: `SLOT_WRITER_SYSTEM_PROMPT`, `PERSONA_WRITER_SYSTEM_PROMPT`, and chat message builder headings/instructions/empty-state labels translated to English with Sora/Miru branding. Screen-based writers (`ScreenSlot Writer`, `ScreenSemanticGate`) preserved untouched.
  - Preservation checks: Pydantic schemas, JSON keys, enum values, size limits, write/merge rules, and caller contracts preserved.
  - `git diff --check`: PASS.
  - Test suite check: 180/180 unit tests passed across slot writer, persona writer, attention, and chat preflight suites.
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 7c229d9ca1fba140b1eb8782b023c3f2841ecfc4` (PASSED).

- **Phase 2B.29 Verification (English Screen Memory Prompts and Writer Contract Repair)**:
  - `memory_prompts_v3.py`: Translated `SCREEN_SEMANTIC_GATE_SYSTEM_PROMPT`, `SCREEN_SLOT_WRITER_SYSTEM_PROMPT`, and builder-sent strings to English with Sora/Miru branding; supported `miru_name` character configuration in chat and screen memory writers; repaired empty-input contract for `call_screen_slot_writer()` returning `ScreenSlotWriterOutput(skipped_reason="empty observation")` without making LLM calls.
  - Preservation checks: Observation text and stored memories in original language; Pydantic models (`NewSlotMeta`, `IntegrationSpec`, `SlotWrite`, `SlotWriterOutput`, `BlockUpdate`, `PersonaWriterOutput`, `NewCommitment`, `ScreenSlotWriterOutput`, `ScreenSemanticGateOutput`), JSON keys, sizes, enums, thresholds, limits, routing, capture behavior, and write rules strictly preserved.
  - Test suite check: Focused test suites (`tests/test_slot_writer_v3_schema.py`, `tests/test_persona_writer_v3_schema.py`, `tests/test_screen_semantic_gate.py`, `tests/test_attention_life_scenarios.py`, `tests/test_chat_preflight_routing.py`) passed successfully (70/70 passed).
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py 6ff34c0081cc687b92de66d795b7860b148c3405` (PASSED).

- **Phase 2B.30 Verification (Finish Memory Writer Translation and Configured Naming)**:
  - `memory_prompts_v3.py`: Translated `SCREEN_SEMANTIC_GATE_SYSTEM_PROMPT` and gate message builder strings (`# Current Observation`, `# Recent Observation History`, `# Recent Post-Gate Writer Outcome Summary`, `# Current Uncompleted DDLs`, `(None)`) to natural English with Sora/Miru branding. Parameterized slot writer, persona writer, screen slot writer, and screen semantic gate system prompts with `{MIRU_NAME}`.
  - `sleep_agent.py`, `core.py`: Wired `miru_name` from character config into `call_persona_writer`, `call_screen_semantic_gate`, and `call_screen_slot_writer`.
  - Preservation checks: Pydantic schemas, JSON contracts, extraction rules, size limits, routing, capture behavior, and upstream extraction behavior strictly preserved.
  - Test suite check: Focused test suites (`tests/test_screen_semantic_gate.py`, `tests/test_care_engine_v3.py`, `tests/test_care_engine_persona.py`) passed successfully (17/17 passed).
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py 34f7d87a88cc3f3688653009448e0ae44b050d57` (PASSED).

- **Phase 2B.31 Verification (English Memory Curator Prompts)**:
  - `memory_prompts_v2.py`: Translated `CURATOR_PLANNER_SYSTEM_PROMPT`, `CURATOR_EXECUTE_MERGE_PROMPT`, `CURATOR_EXECUTE_EDIT_PROMPT`, and `CURATOR_EXECUTE_DELETE_PROMPT` to natural English with Sora/Miru branding (`{MIRU_NAME}` parameterization).
  - `curator.py`: Wired `miru_name` from character configuration into `call_curator_planner`, `call_curator_execute_merge`, `call_curator_execute_edit`, and `call_curator_execute_delete`.
  - Preservation checks: Planner merge/edit/delete/no-op criteria, executor self-checks, type A/B delete placement & value checks, Pydantic validation schemas, JSON keys, enum values, slot IDs, limits, and file operations strictly preserved.
  - Test suite check: Focused curator unit test suites (`test_curator.py`, `test_curator_auto.py`, `test_curator_collision_override.py`, `test_curator_lifecycle.py`, `test_curator_v35_targeted.py`, `test_cost_routing.py`) passed successfully (43/43 passed).
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py 9fd7136dc7eb4e99d3197e4138272e18853136b9` (PASSED).

- **Phase 2B.32 Verification (English Memory Append, Compaction, and Merge Prompts)**:
  - `memory_prompts_v2.py`: Translated Pass 4 append prompts (`PASS4_APPEND_SYSTEM_PROMPT` and `PASS4_APPEND_USER_TEMPLATE`), daily compactor prompts (`SLOT_DAILY_COMPACTOR_SYSTEM_PROMPT` and `SLOT_DAILY_COMPACTOR_USER_TEMPLATE`), and legacy slot merge rewrite prompts (`LEGACY_SLOT_MERGE_SYSTEM_PROMPT` and `LEGACY_SLOT_MERGE_USER_TEMPLATE`) to natural English.
  - Configured character naming (`miru_name` / `{MIRU_NAME}`) integrated across Pass 4, daily compactor, and legacy merge prompts with `_load_miru_name()` helper.
  - Preservation checks: All JSON schemas, enums, limits, paths, retry behavior, file write contracts, and literal references to `## 近期记录` preserved intact.
  - Test suite check: 85/85 passed across curator, Pass 4, slot daily compactor, slot writing, and cost routing suites (`tests/test_curator*.py`, `tests/test_slot_daily_compactor.py`, `tests/test_pass4_summary_truncate.py`, `tests/test_route_with_slot_write.py`, `tests/test_cost_routing.py`).
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `scripts/check_history_append_only.py 253579ed147462bd542f43c03bbe948bc417da79` (PASSED).

- **Phase 2B.33 Verification (English Journal Prompts and Memory Template Corrections)**:
  - `memory_prompts_v2.py`: Translated remaining slot maintenance request templates (`LEGACY_SLOT_MERGE_USER_TEMPLATE`, `PASS4_APPEND_USER_TEMPLATE`, `SLOT_DAILY_COMPACTOR_USER_TEMPLATE`) to natural English and restored character units (`characters`).
  - `prompt.py`: Translated `_build_diary_reformat_prompt()` and chat message type labels to natural English.
  - `journal.py`: Translated journal generation system instructions and context section headers/labels, describing reflective voice without promising journal inaccessibility; kept storage, access control, schedules, and existing entries unchanged.
  - Preservation checks: Configured names, source text, dates, output JSON schema fields, and journal narrative voice preserved intact.
  - Test suite check: 61/61 passed across journal, slot daily compactor, Pass 4 memory append, summary truncation, and curator pipelines.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py f4428a4b306c65fb12d9d9f7d225c91d7deec31e` (PASSED).

- **Phase 2B.34 Verification (English Bundled Persona and Journal Fallbacks)**:
  - `soul.md`: Translated prose and prompt hint values into natural English with Sora as the default character name, preserving parser headings, hint keys, and relationship-stage lookup compatibility.
  - `journal.py`: Translated empty-day journal title, mood label, narrative, and Markdown export labels (`Date`, `Mood`, `Journal`, `Highlights`, `Statistics`, stats labels).
  - Preservation checks: Configured character loading, prompt rendering, journal schema, and backward compatibility with custom personas preserved intact.
  - Test suite check: 34/34 passed across journal, emotion prompt, care engine persona, and persona writer test suites.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py 61b5d7713d74c85196ad6f988f2a9b4d29933936` (PASSED).

- **Phase 2B.35 Verification (Backend Localization Closeout)**:
  - `journal.py`: Corrected empty-day journal title (`A quiet day (Weekday)`) and narrative to be grounded purely in lack of recorded activity and rest/reflection, avoiding claims about screen observation, user whereabouts, or absence reasons.
  - `core_memory.py`: Translated core memory compression prompts, rules, and seed text (`persona_seed`, `human_seed`).
  - `prompt.py`: Translated emotion annotation prompt request text and empty-state labels (`(No emotion records today)`, `(None)`, `(No distinct content in screenshot)`).
  - Preservation checks: Configured character names, existing memory, filenames, limits, initialization behavior, enum values, validation, and injected chat/screenshot summaries preserved intact.
  - Test suite check: 50/50 passed across journal generation, core memory limits, emotion prompts, attention engine, and care & presence suites.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py 82600573077e8d48f3d34a40eded4003a5749cbf` (PASSED).

- **Phase 3.1 Verification (Controlled Local Chat Benchmark Baseline)**:
  - `scripts/benchmark_chat.py`: Updated benchmark script to send messages through Flask `POST /api/chat` and confirm replies via `GET /api/chat/history` using test client and local single-device authentication (`auth.get_or_create_local_single_device_user()`).
  - `tests/test_benchmark_chat.py`: Added focused harness tests verifying successful request routing, history matching, and fallback error string detection.
  - Benchmark Execution & Blocker: Command `python3 scripts/benchmark_chat.py` documented; local Ollama blocker noted (service inactive during test execution, resulting in connection refusal; mock tests verified harness logic).
  - Test suite check: Benchmark unit tests passed successfully.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py 199a046051219f2c394f283119023482488ca659` (PASSED).

- **Phase 3.1A Verification (Verify Fast Mode and Match Benchmark Runs)**:
  - `scripts/benchmark_chat.py`: Added explicit setting and read-back verification of `local_text_chat_enabled` through authenticated `/api/user-settings` route for the disposable benchmark user.
  - `tests/test_benchmark_chat.py`: Added unit tests verifying setting persistence, policy mode resolution (`reactive_fast` vs `v4_pro`), and reply matching.
  - Benchmark Execution & Blocker: Command `python3 scripts/benchmark_chat.py` documented; local Ollama connection error handling verified.
  - Test suite check: 47/47 passed across benchmark, chat routing, companion bootstrap, and user settings test suites.
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py 9c943ebd063040469cc58213ec81cd7d7c182b93` (PASSED).

- **Phase 3.1B Verification (Verify the Benchmark Runner End to End)**:
  - `core.py`: Added `_last_resolved_chat_policy` tracking to observe policy selected within the actual background chat worker with authenticated user context.
  - `scripts/benchmark_chat.py`: Implemented genuine matched comparison using byte-identical prompt text (no timestamp suffixes), equivalent disposable history/user state, alternating execution orders across pairs (`full_first` vs `fast_first`), model warming outside timed intervals, `POST /api/chat` to `GET /api/chat/history` reply confirmation, and separate direct model latency reporting.
  - `tests/test_benchmark_chat.py`: Added comprehensive automated unit test coverage (`test_benchmark_runner_end_to_end_mocked`, `test_benchmark_failure_conditions`) verifying runner execution, mode orders, reply matching, and failure detection (wrong policy, HTTP errors, missing replies, fallback responses).
  - Test suite check: Benchmark unit tests passed successfully (`python3 -m pytest tests/test_benchmark_chat.py`).
  - Git diff check: PASS (zero unexpected deletions, clean whitespace).
  - History Prefix Integrity: Enforced by `python3 scripts/check_history_append_only.py 69a5c90a87abe047cc58f7f4d27dd9011828566f` (PASSED).
