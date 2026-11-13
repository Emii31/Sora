# Phase 3.2B — Keep Provider Credentials and Model Selections Together

## 1. Verify the starting checkpoint
- Read CLAUDE.md and the Phase 3 records.
- Check Git status and preserve unrelated work.
- The last verified local HEAD is 5735c90f90e579274e3ff8bcb39b051172c0a8ab.

## 2. Use the same provider resolution for setup and runtime
- In ai_config.py, resolve the endpoint and credential as one pair for discovery, connection tests, and inference.
- When the endpoint changes, require a valid replacement credential or leave the connection in a setup-required state.
- Treat omitted, blank, and null credentials consistently.
- Preserve valid existing configurations, loopback HTTP, remote HTTPS, and owner authorization.
- Verify with mocked clients that no request carries a credential belonging to a different endpoint.

## 3. Bind automatic selections to their connection
- Track automatically discovered model IDs separately from explicit overrides.
- Invalidate automatic selections when their connection changes.
- Use provider capability metadata or a bounded setup-time probe to verify text or image support.
- If capability is unknown or selection is ambiguous, report setup required.
- Keep discovery out of config reads and chat requests.
- Verify that a working alternate base URL is reused by runtime calls without creating a tier override for shared settings.

## 4. Verify and publish
- Run focused configuration, discovery, and owner API tests with disposable data and mocked network calls.
- Record exact commands and counts.
- Update docs/STATUS.md, add docs/phases/PHASE_03_02B.md, and append the session and verification logs.
- Review the staged diff and run history-prefix and whitespace checks.
- Push only to Emii31/Sora on origin/main using a normal fast-forward push.
- Verify the full local and live remote hashes.
- Keep benchmark isolation, live Ollama timings, and app work deferred.
- Stop after Phase 3.2B.