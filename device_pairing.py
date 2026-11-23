"""Single-use grants and independently revocable credentials for local phones."""

from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

PHONE_TOKEN_PREFIX = "sora-phone-"
CODE_LIFETIME_SECONDS = 300
_CODE = re.compile(r"[A-Za-z0-9_-]{32}")
_TOKEN = re.compile(PHONE_TOKEN_PREFIX + r"[A-Za-z0-9_-]{43}")


def enabled():
    return os.environ.get("SORA_LOCAL_PAIRING") == "1"


def direct_loopback(req):
    if req.remote_addr not in {"127.0.0.1", "::1"}:
        return False
    try:
        return urlsplit(req.host_url).hostname in {"127.0.0.1", "::1", "localhost"}
    except ValueError:
        return False


def protected_connection(req):
    return req.is_secure or direct_loopback(req)


def _digest(secret):
    return sha256(secret.encode("ascii")).hexdigest()


@contextmanager
def _store(admin_dir):
    directory = Path(admin_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = directory / "local_pairing.sqlite3"
    try:
        fd = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(fd)
    conn = sqlite3.connect(database)
    try:
        with conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS codes (
                digest TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at INTEGER NOT NULL
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS phones (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, digest TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, created_at INTEGER NOT NULL
            )""")
            yield conn
    finally:
        conn.close()


def issue_code(admin_dir, user_id):
    code = secrets.token_urlsafe(24)
    now = int(time.time())
    expires = now + CODE_LIFETIME_SECONDS
    with _store(admin_dir) as conn:
        conn.execute("DELETE FROM codes WHERE user_id = ? OR expires_at <= ?", (user_id, now))
        conn.execute("INSERT INTO codes VALUES (?, ?, ?)", (_digest(code), user_id, expires))
    return code, expires


def redeem_code(admin_dir, code, name, active_account):
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        return None
    with _store(admin_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        now = int(time.time())
        grant = conn.execute("SELECT user_id FROM codes WHERE digest = ? AND expires_at > ?",
                             (_digest(code), now)).fetchone()
        if not grant or not active_account(grant[0]):
            return None
        user_id = grant[0]
        token = PHONE_TOKEN_PREFIX + secrets.token_urlsafe(32)
        device_id = secrets.token_hex(16)
        conn.execute("INSERT INTO phones VALUES (?, ?, ?, ?, ?)",
                     (device_id, user_id, _digest(token), name, now))
        conn.execute("DELETE FROM codes WHERE digest = ?", (_digest(code),))
    return {"user_id": user_id, "device_id": device_id, "token": token}


def user_for_token(admin_dir, token):
    if not _TOKEN.fullmatch(token):
        return None
    with _store(admin_dir) as conn:
        row = conn.execute("SELECT user_id FROM phones WHERE digest = ?", (_digest(token),)).fetchone()
    return row[0] if row else None


def list_phones(admin_dir, user_id):
    with _store(admin_dir) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(
            "SELECT id, name, created_at FROM phones WHERE user_id = ? ORDER BY created_at, id", (user_id,))]


def revoke_phone(admin_dir, user_id, device_id):
    with _store(admin_dir) as conn:
        return conn.execute("DELETE FROM phones WHERE user_id = ? AND id = ?", (user_id, device_id)).rowcount == 1
