# CLAUDE.md - Sora Companion Project Rules

1. On every new session, read CLAUDE.md, docs/STATUS.md, docs/DECISIONS.md, and the current phase document (docs/phases/) before working.
2. Work only on the authorized phase. Do not automatically start the next phase.
3. Keep changes small, preserve existing user changes, and inspect Git diffs before claiming completion.
4. Use isolated project dependencies. No sudo, global installs, system Python package changes, or downloaded installer execution during this phase.
5. Do not modify or expose existing credentials.
6. Validate behavior with checks appropriate to each change. Distinguish static inspection, tests, and actual GUI/device checks.
7. After each work session AND each completed phase, update docs/STATUS.md, docs/SESSION_LOG.md, docs/VERIFICATION.md, and the phase document. Update docs/ARCHITECTURE.md and docs/DECISIONS.md when decisions change.
8. Record exact commands, exit results, changed files, unresolved issues, and the next action, with secrets redacted.
9. Use statuses: planned / in progress / blocked / implemented awaiting verification / verified.
10. Preserve upstream licenses and third-party asset terms. Avoid blind global search-and-replace for translation or renaming.
11. Provide a concise handoff the owner can paste to the supervising architect. Do not claim an independent review has happened.
12. Do not commit, push, enable autostart, or expose network services as part of Phase 0.

## Critical Editing Guardrails (Added 2026-11-07 post-recovery)
13. **Never replace a large existing file with an abbreviated implementation, placeholder, stub, or omitted sections.**
14. **Translate through small contextual patches.**
15. **Preserve unrelated code and session history.**
16. **Before editing, preserve a recoverable copy of files being changed, including untracked documentation.**
17. **After every edit batch, inspect diff statistics and actual hunks.**
18. **Unexpected large deletions require immediate investigation and recovery, not continued work or a success claim.**
19. **HTTP 200 and syntax validity do not establish preserved functionality.**
20. **Select tests relevant to changed behavior.**
21. **Append session records; do not replace earlier entries.**

## Git Publishing Policy (Sora-Only)
22. **Commit locally in this Sora working repository; push only to `origin` (`https://github.com/Emii31/Sora.git`).**
23. **`upstream` (`https://github.com/kiyotakali/Miru.git`) is strictly fetch-only (push URL disabled). Never create upstream PRs, issues, comments, or send messages to upstream maintainers.**
24. **At each completed and validated task, create a reviewed checkpoint and push it to the user's repository (`origin`).**
25. **Never commit or push secrets, runtime memory, credentials, or recovery dumps.**
26. **Never use force-push or mirror-push; only fast-forward pushes to `origin/main`.**
27. **Rejected or damaged work must be fully recovered and verified before publishing.**
28. **Preserve upstream license and third-party attribution.**
