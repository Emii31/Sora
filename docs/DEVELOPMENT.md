# DEVELOPMENT.md - Sora Development Environment

## Environment Setup
- **Interpreter**: Python 3.11.18 (System provided `/usr/bin/python3.11`).
- **Isolation**: Project-local `.venv`.
- **Environment Path**: `/mnt/data/Companion/Miru/.venv/`

To recreate:
```bash
/usr/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt
```

## Testing
- **Command**: `.venv/bin/python -m pytest tests/test_prompt_json_parse.py tests/test_no_secret_leakage.py tests/test_identity_aliases_cascade.py -q`
- **Result**: 21 passed.

## Local Smoke Testing
To run an isolated backend smoke test on localhost only (`127.0.0.1:5000`) using a managed disposable `DATA_DIR` and foreground launcher lifecycle:
```bash
.venv/bin/python scripts/dev_local_smoke.py
```
URLs for local access:
- Marketing page: `http://127.0.0.1:5000/`
- Companion interface: `http://127.0.0.1:5000/app`
- Welcome / Login interface: `http://127.0.0.1:5000/login`
- Health check: `http://127.0.0.1:5000/api/health`
