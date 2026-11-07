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

## 2026-11-07 (Phase 2B.1: Static App Navigation Translation)
- Translated static navigation text in `templates/index.html` to English with Sora branding
- Changes: 26 insertions, 26 deletions (net 0), 12807 lines preserved
- Header brand heading: Miru → Sora
- Header buttons: 设置→Settings, 刷新数据→Refresh, 启动桌宠→Desktop Pet, 退出 ContextLife→Exit
- Sidebar nav labels: 对话→Chat, 伴随面板→Companion, 记忆→Memory, 情绪→Emotions, 我的心情→My Mood
- Mobile tab bar labels: 对话→Chat, 记忆→Memory, 设置→Settings
- Settings modal: 全局设置→Global Settings, 关闭→Close, 身份→Identity, 角色管理→Characters, 模型→AI Models, 系统→System
- All preservation checks passed: script/style blocks byte-for-byte identical, 124 DOM IDs preserved, 109 onclick handlers preserved, 12 URLs preserved, 3 aria-labels preserved
- Pre-edit backup saved at `/mnt/data/Companion/recovery/20261107_emergency_recovery/index_before_phase_2B_1_patch.html`
