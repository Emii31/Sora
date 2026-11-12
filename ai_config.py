"""3-tier AI provider configuration (admin-managed, global).

Tiers:
  - vision  : screenshot VLM (cheap multimodal)
  - chat    : main conversation (capable multimodal — user may upload images)
  - memory  : background memory writes (capable text; helpers accept images=
              for forward-compat but current callers don't pass any)

All tiers use OpenAI-compatible endpoints. Anthropic SDK is no longer required —
Anthropic-hosted models can still be used via their OpenAI-compatible /v1 path.

Storage:
  data/_admin/ai_config.json — single global file, admin-only
  Per-user override is intentionally removed (users share the same backend).

Env-var fallback (used on first boot when ai_config.json doesn't exist):
  AI_VISION_HOST / AI_VISION_KEY / AI_VISION_MODEL
  AI_CHAT_HOST   / AI_CHAT_KEY   / AI_CHAT_MODEL
  AI_MEMORY_HOST / AI_MEMORY_KEY / AI_MEMORY_MODEL

Hot-reload: any successful update clears the in-memory cache so the next
LLM call picks up new credentials without restarting Flask.
"""

from __future__ import annotations

import ipaddress
import json
import os
import threading
from urllib.parse import urlsplit


TIERS = ("vision", "chat", "memory")
TIER_LABELS = {
    "vision": "Vision model",
    "chat": "Chat model",
    "memory": "Memory model",
}

# Per-tier env-var fallback (read once on cache miss).
_ENV_VARS = {
    "vision": ("AI_VISION_HOST", "AI_VISION_KEY", "AI_VISION_MODEL"),
    "chat":   ("AI_CHAT_HOST",   "AI_CHAT_KEY",   "AI_CHAT_MODEL"),
    "memory": ("AI_MEMORY_HOST", "AI_MEMORY_KEY", "AI_MEMORY_MODEL"),
}

# Hard-coded fallback if neither saved config nor env vars are present.
# Empty values cause callers to surface the user-facing "模型配置还没有完成" copy
# rather than silently failing.
_DEFAULT_PER_TIER = {
    "vision": {"host": "", "api_key": "", "model": "", "supports_images": True},
    "chat":   {"host": "", "api_key": "", "model": "", "supports_images": True},
    "memory": {"host": "", "api_key": "", "model": "", "supports_images": False},
}

# Per-tier max_tokens defaults.
_DEFAULT_MAX_TOKENS = {
    "vision": 50000,
    "chat":   50000,
    "memory": 65536,
}

_lock = threading.RLock()  # RLock — get_tier_client calls get_tier_config inside the lock
_cache: dict[str, dict] | None = None  # tier → resolved config
_client_cache: dict[str, object] = {}  # tier → openai.OpenAI


# ---------------------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------------------

def _data_dir() -> str:
    return os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))


def _config_path() -> str:
    return os.path.join(_data_dir(), "_admin", "ai_config.json")


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(_config_path()), exist_ok=True)


# ---------------------------------------------------------------------------
# Host normalization
# ---------------------------------------------------------------------------

_KNOWN_HOST_PREFIX = {
    "openrouter.ai": "openrouter.ai/api",
    "open.bigmodel.cn": "open.bigmodel.cn/api/paas/v4",
    "generativelanguage.googleapis.com": "generativelanguage.googleapis.com/v1beta/openai",
}

_CHAT_COMPLETIONS_ENDPOINT_SUFFIX = "/chat/completions"


def _strip_chat_completions_endpoint(host: str) -> str:
    lower = host.lower().rstrip("/")
    if not lower.endswith(_CHAT_COMPLETIONS_ENDPOINT_SUFFIX):
        return host
    return host[: -len(_CHAT_COMPLETIONS_ENDPOINT_SUFFIX)].rstrip("/")


def _normalize_host(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    has_scheme = "://" in raw
    parsed = urlsplit(raw if has_scheme else f"https://{raw}")
    scheme = parsed.scheme.lower() if has_scheme else ""
    netloc = (parsed.netloc or "").strip().lower()
    path = (parsed.path or "").strip().rstrip("/")
    if netloc:
        host = netloc + path if path else netloc
    else:
        host = parsed.path.strip().rstrip("/")
    host = host.rstrip("/")
    host = _strip_chat_completions_endpoint(host)
    host_key = host.lower()
    if host_key == "openrouter.ai/v1":
        host = "openrouter.ai/api"
    elif host_key in _KNOWN_HOST_PREFIX:
        host = _KNOWN_HOST_PREFIX[host_key]

    if _is_loopback(host) and scheme == "https":
        return f"https://{host}"
    return host


def _is_loopback(host_or_url: str) -> bool:
    raw = str(host_or_url).strip()
    if not raw:
        return False
    if not "://" in raw:
        raw = f"//{raw}"
    parsed = urlsplit(raw)
    netloc = parsed.netloc or parsed.path
    if "[" in netloc:
        try:
            end_idx = netloc.index("]")
            hostname = netloc[1:end_idx].lower()
        except ValueError:
            hostname = netloc.strip("[]").lower()
    else:
        hostname = netloc.split(":")[0].lower()

    if hostname == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_loopback
    except ValueError:
        return False


def _base_url_scheme(host: str) -> str:
    if str(host).lower().startswith("https://"):
        return "https"
    if _is_loopback(host):
        return "http"
    return "https"


def _legacy_openai_base_url(normalized: str) -> str:
    if "://" in normalized:
        base = normalized
    else:
        scheme = _base_url_scheme(normalized)
        base = f"{scheme}://{normalized}"
    lower = normalized.lower().rstrip("/")
    if lower.endswith("/v1") or lower.endswith("/v1beta/openai"):
        return base
    return f"{base}/v1"


def _prefer_legacy_base_url(normalized: str) -> bool:
    if "://" in normalized:
        parsed = urlsplit(normalized)
    else:
        scheme = _base_url_scheme(normalized)
        parsed = urlsplit(f"{scheme}://{normalized}")
    path = (parsed.path or "").rstrip("/").lower()
    if not path:
        return True
    if normalized.lower() == "openrouter.ai/api":
        return True
    if path.endswith("/openai"):
        return True
    return False


def _openai_base_url_candidates(host: str) -> list[str]:
    normalized = _normalize_host(host)
    if not normalized:
        return []
    if "://" in normalized:
        exact = normalized
    else:
        scheme = _base_url_scheme(normalized)
        exact = f"{scheme}://{normalized}"
    legacy = _legacy_openai_base_url(normalized)
    ordered = [legacy, exact] if _prefer_legacy_base_url(normalized) else [exact, legacy]
    return list(dict.fromkeys(ordered))


def _openai_base_url_from_host(host: str) -> str:
    candidates = _openai_base_url_candidates(host)
    return candidates[0] if candidates else ""


_PING_PIXEL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAIAAABMXPacAAABKklEQVR42u3ZvQnCQBiA4YukFEdwhxCsU9mIQwRiI7iBK7iDrZUIYuUIFgFrm2ySCQR/ityR560T7sLDd5Ak69Z1SLmm2ie9/0kQAAACAEAAAAgAAAEAIAAABACAAAAQAAACAEAAAAgAAAEAIAAABACAAAAQAAACAEAAAAgAAAEAoI/LY9jE/Hr8+d77H+suDy8T4AgSAAACAEAAAAgAAAEIvgXFV1Esvrq+bR8mQAAACAAAAQCgN+8B28108E3cBlr3XDYmwBEkAAAEAIAA+B8Qcal83zcBAAQAgAAAEAAAAgBAACIuW112ST/AafY0AQIAQAAACAAAAQAgAAAEAIAAABAAAAIAQAAACAAAAQAgAAAEAIAAAAAgAAAEAIAAABAAAAIAQADGUg9XjhKyLWierQAAAABJRU5ErkJggg=="
)


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "***" + value[-4:]


def _safe_error_message(exc: Exception, api_key: str = "", limit: int = 300) -> str:
    msg = str(exc)
    if api_key:
        msg = msg.replace(api_key, _mask_secret(api_key))
    return msg[:limit]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load_saved() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _save_atomic(data: dict) -> None:
    _ensure_dir()
    path = _config_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _persist_resolved_base_url(tier: str, base_url: str) -> None:
    normalized = _normalize_host(base_url)
    if tier not in TIERS or not normalized:
        return

    with _lock:
        saved = _load_saved()
        tiers = saved.get("tiers")
        if not isinstance(tiers, dict):
            tiers = {}
            saved["tiers"] = tiers
        tier_saved = tiers.get(tier)
        if not isinstance(tier_saved, dict):
            tier_saved = {}
            tiers[tier] = tier_saved
        if tier_saved.get("host") == normalized:
            return

        tier_saved["host"] = normalized
        from datetime import datetime as _dt
        saved["updated_at"] = _dt.now().isoformat(timespec="seconds")
        saved["version"] = 2
        _save_atomic(saved)

    invalidate_cache()


# ---------------------------------------------------------------------------
# Automatic Model Discovery
# ---------------------------------------------------------------------------

def discover_provider_models(host: str, api_key: str) -> list[str]:
    """Query provider model list via OpenAI-compatible endpoint."""
    if not host or not api_key:
        return []
    import openai
    candidates = _openai_base_url_candidates(host)
    for base_url in candidates:
        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=5.0)
            models = client.models.list()
            model_ids = []
            for m in models:
                mid = getattr(m, "id", str(m))
                if mid:
                    model_ids.append(mid)
            if model_ids:
                return model_ids
        except Exception:
            continue
    return []


# ---------------------------------------------------------------------------
# Resolution: tier override → shared provider → env → default
# ---------------------------------------------------------------------------

def _resolve_tier(tier: str, saved: dict) -> dict:
    """Resolve one tier's config from saved JSON (tier → shared) → env vars → defaults."""
    if tier not in TIERS:
        raise ValueError(f"unknown tier: {tier}")

    shared_saved = saved.get("shared", {}) or {}
    shared_host = _normalize_host(shared_saved.get("host", ""))
    shared_key = str(shared_saved.get("api_key", "")).strip()

    tier_saved = (saved.get("tiers", {}) or {}).get(tier, {}) or {}
    env_host_var, env_key_var, env_model_var = _ENV_VARS[tier]
    defaults = _DEFAULT_PER_TIER[tier]

    has_tier_host = bool(tier_saved.get("host"))
    has_tier_key = bool(tier_saved.get("api_key"))

    if has_tier_host or has_tier_key:
        host = tier_saved.get("host", "") or os.environ.get(env_host_var, "") or defaults["host"]
        api_key = tier_saved.get("api_key", "") or os.environ.get(env_key_var, "") or defaults["api_key"]
    elif shared_host and shared_key:
        # Resolve endpoint and credential together from shared provider
        host = shared_host
        api_key = shared_key
    else:
        host = os.environ.get(env_host_var, "") or os.environ.get("AI_HOST", "") or defaults["host"]
        api_key = os.environ.get(env_key_var, "") or os.environ.get("AI_API_KEY", "") or defaults["api_key"]

    model = tier_saved.get("model") or os.environ.get(env_model_var, "") or os.environ.get("AI_MODEL", "") or defaults["model"]
    supports_images = bool(tier_saved.get("supports_images", defaults["supports_images"]))

    normalized_host = _normalize_host(host)
    trimmed_key = str(api_key or "").strip()
    trimmed_model = str(model or "").strip()

    # Automatic model selection if model is empty and host+key are present
    if not trimmed_model and normalized_host and trimmed_key:
        discovered = discover_provider_models(normalized_host, trimmed_key)
        if discovered:
            if tier == "vision":
                vision_models = [m for m in discovered if any(k in m.lower() for k in ("vision", "vl", "omni", "multimodal", "gpt-4o", "sonnet"))]
                if vision_models:
                    trimmed_model = vision_models[0]
                    supports_images = True
            else:
                text_models = [m for m in discovered if any(k in m.lower() for k in ("instruct", "chat", "gpt", "claude", "qwen", "llama", "deepseek", "flash", "pro"))]
                if text_models:
                    trimmed_model = text_models[0]
                else:
                    trimmed_model = discovered[0]

    return {
        "host": normalized_host,
        "api_key": trimmed_key,
        "model": trimmed_model,
        "supports_images": supports_images,
        "max_tokens": int(tier_saved.get("max_tokens") or _DEFAULT_MAX_TOKENS[tier]),
    }


def _ensure_cache() -> None:
    global _cache
    if _cache is not None:
        return
    saved = _load_saved()
    _cache = {tier: _resolve_tier(tier, saved) for tier in TIERS}


def invalidate_cache() -> None:
    """Drop in-memory caches (config + clients). Called after every update."""
    global _cache, _client_cache
    with _lock:
        _cache = None
        _client_cache = {}


# ---------------------------------------------------------------------------
# Public read API
# ---------------------------------------------------------------------------

def get_tier_config(tier: str) -> dict:
    if tier not in TIERS:
        raise ValueError(f"unknown tier: {tier}")
    with _lock:
        _ensure_cache()
        return dict(_cache[tier])


def resolve_max_tokens(tier: str, requested: int | None = None) -> int:
    cfg = get_tier_config(tier)
    configured = int(cfg.get("max_tokens") or _DEFAULT_MAX_TOKENS[tier])
    if requested is None:
        return configured
    try:
        wanted = int(requested)
    except (TypeError, ValueError):
        return configured
    return max(1, min(configured, wanted))


def get_tier_client(tier: str):
    import openai

    with _lock:
        if tier in _client_cache:
            return _client_cache[tier]
        cfg = get_tier_config(tier)
        tier_label = TIER_LABELS.get(tier, tier)
        if not cfg["api_key"]:
            raise RuntimeError(
                f"Model configuration incomplete: {tier_label} missing API Key. "
                f"Please fill in the service URL, model name, and API Key in the Model settings page in Sora."
            )
        if not cfg["host"]:
            raise RuntimeError(
                f"Model configuration incomplete: {tier_label} missing service URL. "
                f"Please fill in the service URL, model name, and API Key in the Model settings page in Sora."
            )
        client = openai.OpenAI(
            api_key=cfg["api_key"],
            base_url=_openai_base_url_from_host(cfg["host"]),
            timeout=120.0,
        )
        _client_cache[tier] = client
        return client


def get_public_config() -> dict:
    """Return shared config and all tiers with masked api_key. For admin UI display."""
    with _lock:
        _ensure_cache()
        saved = _load_saved()
        shared_saved = saved.get("shared", {}) or {}
        shared_host = shared_saved.get("host", "")
        shared_key = str(shared_saved.get("api_key", "")).strip()

        out = {
            "version": 2,
            "shared": {
                "host": shared_host,
                "api_key_masked": _mask_secret(shared_key),
                "has_api_key": bool(shared_key),
            },
            "tiers": {}
        }
        for tier in TIERS:
            cfg = _cache[tier]
            out["tiers"][tier] = {
                "host": cfg["host"],
                "api_key_masked": _mask_secret(cfg["api_key"]),
                "has_api_key": bool(cfg["api_key"]),
                "model": cfg["model"],
                "supports_images": cfg["supports_images"],
                "max_tokens": cfg["max_tokens"],
            }
        return out


# ---------------------------------------------------------------------------
# Public write API
# ---------------------------------------------------------------------------

def update_shared_config(payload: dict) -> dict:
    """Update shared provider configuration."""
    if not isinstance(payload, dict):
        return {"ok": False, "error": "payload must be an object"}
    with _lock:
        saved = _load_saved()
        if "shared" not in saved or not isinstance(saved.get("shared"), dict):
            saved["shared"] = {}
        cur = saved["shared"]

        if payload.get("clear_api_key"):
            cur["api_key"] = ""
        elif "api_key" in payload and payload["api_key"] is not None:
            api_key = str(payload["api_key"]).strip()
            if api_key:
                cur["api_key"] = api_key

        if "host" in payload and payload["host"] is not None:
            host = _normalize_host(payload["host"])
            if not host:
                return {"ok": False, "error": "host cannot be empty"}
            cur["host"] = host

        saved["shared"] = cur
        from datetime import datetime as _dt
        saved["updated_at"] = _dt.now().isoformat(timespec="seconds")
        saved["version"] = 2
        _save_atomic(saved)

    invalidate_cache()
    return {"ok": True, "config": get_public_config()}


def update_tier_config(tier: str, payload: dict) -> dict:
    """Update one tier. Returns {ok: bool, error?: str, config?: dict}."""
    if tier not in TIERS:
        return {"ok": False, "error": f"unknown tier: {tier}"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "payload must be an object"}

    with _lock:
        saved = _load_saved()
        if "tiers" not in saved or not isinstance(saved.get("tiers"), dict):
            saved["tiers"] = {}
        if tier not in saved["tiers"]:
            saved["tiers"][tier] = {}
        cur = saved["tiers"][tier]

        if payload.get("clear_api_key"):
            cur["api_key"] = ""
        elif "api_key" in payload and payload["api_key"] is not None:
            api_key = str(payload["api_key"]).strip()
            if api_key:
                cur["api_key"] = api_key

        if "host" in payload and payload["host"] is not None:
            host = _normalize_host(payload["host"])
            if not host:
                return {"ok": False, "error": "host cannot be empty"}
            cur["host"] = host

        if "model" in payload and payload["model"] is not None:
            model = str(payload["model"]).strip()
            if not model:
                return {"ok": False, "error": "model cannot be empty"}
            cur["model"] = model

        if "supports_images" in payload:
            cur["supports_images"] = bool(payload["supports_images"])

        if "max_tokens" in payload and payload["max_tokens"] is not None:
            try:
                mt = int(payload["max_tokens"])
                if mt < 1 or mt > 1_000_000:
                    return {"ok": False, "error": "max_tokens out of range"}
                cur["max_tokens"] = mt
            except (TypeError, ValueError):
                return {"ok": False, "error": "max_tokens must be integer"}

        saved["tiers"][tier] = cur
        from datetime import datetime as _dt
        saved["updated_at"] = _dt.now().isoformat(timespec="seconds")
        saved["version"] = 2

        _save_atomic(saved)

    invalidate_cache()
    return {"ok": True, "config": get_public_config()}


def ping_tier(tier: str, timeout_seconds: int = 15) -> dict:
    """Make a minimal real API call to verify a tier's config works."""
    try:
        cfg = get_tier_config(tier)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    if not cfg["api_key"]:
        tier_label = TIER_LABELS.get(tier, tier)
        return {"ok": False, "tier": tier, "error": f"{tier_label} missing API Key"}
    if not cfg["host"]:
        tier_label = TIER_LABELS.get(tier, tier)
        return {"ok": False, "tier": tier, "error": f"{tier_label} missing service URL"}
    if not cfg["model"]:
        tier_label = TIER_LABELS.get(tier, tier)
        return {"ok": False, "tier": tier, "error": f"{tier_label} missing model name"}

    import time
    import openai

    if tier == "vision" and not cfg.get("supports_images", True):
        return {
            "ok": False,
            "tier": tier,
            "model": cfg["model"],
            "host": cfg["host"],
            "error": "Vision model must support image input. Please enable image capabilities or switch to a multimodal model.",
        }

    messages = [{"role": "user", "content": "Reply with OK."}]
    if tier == "vision":
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Reply with OK after checking this 128x128 test image."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{_PING_PIXEL_PNG_B64}",
                    },
                },
            ],
        }]

    from prompt import _vendor_extra_body
    candidates = _openai_base_url_candidates(cfg["host"])
    t0 = time.time()
    for index, base_url in enumerate(candidates):
        try:
            client = openai.OpenAI(
                api_key=cfg["api_key"],
                base_url=base_url,
                timeout=timeout_seconds,
            )
            extra_body = _vendor_extra_body(cfg["model"], _normalize_host(base_url))
            client.chat.completions.create(
                model=cfg["model"],
                max_tokens=64,
                messages=messages,
                extra_body=extra_body,
            )
            elapsed_ms = int((time.time() - t0) * 1000)
            _persist_resolved_base_url(tier, base_url)
            return {
                "ok": True,
                "tier": tier,
                "model": cfg["model"],
                "host": _normalize_host(base_url),
                "elapsed_ms": elapsed_ms,
            }
        except Exception as exc:
            http_status = getattr(exc, "status_code", None)
            response = getattr(exc, "response", None)
            if http_status is None and response is not None:
                http_status = getattr(response, "status_code", None)
            has_fallback = index + 1 < len(candidates)
            if http_status in (404, 405) and has_fallback:
                continue
            return {
                "ok": False,
                "tier": tier,
                "model": cfg["model"],
                "host": cfg["host"],
                "http_status": http_status,
                "error_type": exc.__class__.__name__,
                "error": _safe_error_message(exc, cfg["api_key"]),
            }

    return {
        "ok": False,
        "tier": tier,
        "model": cfg["model"],
        "host": cfg["host"],
        "error": "No available OpenAI-compatible Base URL",
    }


# ---------------------------------------------------------------------------
# Backward-compat shims
# ---------------------------------------------------------------------------

def get_runtime_config() -> dict:
    cfg = get_tier_config("chat")
    return {
        "provider": "openai",
        "api_key": cfg["api_key"],
        "host": cfg["host"],
        "model": cfg["model"],
    }


def update_public_config(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid payload"}
    return update_tier_config("chat", payload)


def ping_provider(timeout_seconds: int = 12) -> dict:
    return ping_tier("chat", timeout_seconds)
