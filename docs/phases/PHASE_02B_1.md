# PHASE 2B.1: Static Main-App Navigation Translation

**Goal:** Translate static HTML navigation text in `templates/index.html` to English with Sora branding, preserving all markup, IDs, handlers, icons, classes, and behavior.

**Status:** Implemented awaiting verification

**Changes made:**
- Document title: `Miru` → `Sora`
- Desktop header brand heading: `Miru` → `Sora`
- Header button titles and labels: Settings, Refresh, Desktop Pet, Exit
- Sidebar navigation labels: Chat, Companion, Memory, Emotions, My Mood
- Mobile tab bar labels: Chat, Memory, Settings
- Settings modal heading, close button, and top-level tab labels:
  - Global Settings, Close
  - Identity, Characters, AI Models, Devices, System

**Scope:**
- Translated ONLY static HTML visible text in navigation/header/sidebar/modal regions
- No chat composer, embedded login, onboarding, settings contents, backend files, CSS, or JavaScript changes
- No translation overlays, replacement scripts, stubs, or libraries added
- No file reformatting

**Preservation checks:**
- All 5 script blocks byte-for-byte identical
- All 3 style blocks byte-for-byte identical
- 124 DOM element IDs unchanged
- 109 onclick handlers identical
- 12 external resource URLs unchanged
- 3 aria-label attributes unchanged
- Line count unchanged at 12807
- `git diff --check`: PASS

**Backup evidence:** `/mnt/data/Companion/recovery/20261107_emergency_recovery/index_before_phase_2B_1_patch.html`

**Verification evidence:** `docs/verification/phase_02B_1/verification_output.txt`

**Remaining work:** Dynamic copy and other UI regions outstanding (settings panel contents, chat composer, embedded login, onboarding, character names).
