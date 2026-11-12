import os
import base64
import json
import ast
import random
import re
import time
from datetime import datetime

from character import get_config
from prompt_identity import (
    normalize_character_section,
    resolve_user_entity_label,
    safe_user_address,
)
import ai_config

# Backward-compat shim: legacy callers expected `get_runtime_config()` and
# `DEFAULT_MODEL`. After 3-tier migration, runtime config is per-tier;
# legacy `get_runtime_config()` now returns the chat tier as a default,
# and `DEFAULT_MODEL` is unused (kept as empty string for any rare reader).
get_runtime_config = ai_config.get_runtime_config
DEFAULT_MODEL = ""


# ---------------------------------------------------------------------------
# LLM usage logging — one JSONL row per call, for cost / consumption analysis.
# Cheap (one open/write/close per call); failure must never break the LLM call.
# ---------------------------------------------------------------------------
_USAGE_LOG_PATH = None

def _usage_get(obj, key, default=None):
    """Best-effort field access for OpenAI SDK objects, dicts and model_extra."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    val = getattr(obj, key, default)
    if val is not None:
        return val
    extra = getattr(obj, "model_extra", None)
    if isinstance(extra, dict) and key in extra:
        return extra.get(key, default)
    try:
        return obj[key]
    except Exception:
        return default

def _usage_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default

def _get_usage_log_path():
    global _USAGE_LOG_PATH
    if _USAGE_LOG_PATH is None:
        base = os.environ.get("DATA_DIR", "data")
        admin_dir = os.path.join(base, "_admin")
        try:
            os.makedirs(admin_dir, exist_ok=True)
        except Exception:
            pass
        _USAGE_LOG_PATH = os.path.join(admin_dir, "llm_usage.jsonl")
    return _USAGE_LOG_PATH

def _log_llm_usage(tier, model, response, **meta):
    try:
        usage = _usage_get(response, "usage")
        if not usage:
            return
        prompt_tokens = _usage_int(_usage_get(usage, "prompt_tokens"))
        completion_tokens = _usage_int(_usage_get(usage, "completion_tokens"))
        total_tokens = _usage_int(_usage_get(usage, "total_tokens"))

        prompt_details = _usage_get(usage, "prompt_tokens_details")
        completion_details = _usage_get(usage, "completion_tokens_details")

        cache_hit = _usage_int(_usage_get(usage, "prompt_cache_hit_tokens"))
        cache_miss = _usage_int(_usage_get(usage, "prompt_cache_miss_tokens"))
        cached_tokens = _usage_int(_usage_get(prompt_details, "cached_tokens"))
        if cache_hit <= 0 and cached_tokens > 0:
            cache_hit = cached_tokens
        if cache_miss <= 0 and prompt_tokens > 0 and cache_hit > 0:
            cache_miss = max(prompt_tokens - cache_hit, 0)

        reasoning_tokens = _usage_int(_usage_get(usage, "reasoning_tokens"))
        if reasoning_tokens <= 0:
            reasoning_tokens = _usage_int(_usage_get(completion_details, "reasoning_tokens"))

        rec = {
            "ts": time.time(),
            "tier": tier,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "prompt_cache_hit_tokens": cache_hit,
            "prompt_cache_miss_tokens": cache_miss,
            "reasoning_tokens": reasoning_tokens,
        }
        for k, v in meta.items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                rec[k] = v
            else:
                rec[k] = str(v)
        try:
            from flask import g
            uid = getattr(g, "user_id", None)
            if uid:
                rec["user_id"] = uid
        except Exception:
            pass
        with open(_get_usage_log_path(), "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging must never break the LLM call


def _extract_json_block(text):
    """Extract the outermost JSON object or array from text, ignoring any trailing noise.

    LLMs sometimes append explanatory text after the JSON block (e.g., '已经写好了').
    This function finds the matching closing brace/bracket and strips the rest.
    """
    text = text.strip()
    start = -1
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            start = i
            break
    if start == -1:
        return text

    open_ch = text[start]
    close_ch = '}' if open_ch == '{' else ']'
    depth = 0
    end = -1
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                end = i
                break
    return text[start:end + 1] if end != -1 else text


def _strip_code_fences(text):
    raw = (text or "").strip()
    if not raw.startswith("```"):
        return raw
    lines = raw.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _repair_common_json_issues(text):
    """Best-effort repair for frequent LLM JSON formatting mistakes."""
    repaired = (text or "").strip()
    # Normalize smart quotes to avoid malformed keys/strings.
    repaired = repaired.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    repaired = _strip_json_comments(repaired)
    # Remove trailing commas before object/array close.
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)

    # Insert missing commas between adjacent key/value lines.
    lines = repaired.splitlines()
    if len(lines) > 1:
        out = []
        for idx, line in enumerate(lines):
            cur = line.rstrip()
            nxt = lines[idx + 1].lstrip() if idx + 1 < len(lines) else ""
            if idx + 1 < len(lines):
                cur_stripped = cur.rstrip()
                if (
                    cur_stripped
                    and not cur_stripped.endswith((",", "{", "[", ":"))
                    and not nxt.startswith(("}", "]"))
                    and nxt.startswith(('"', "{", "["))
                    and re.search(r'("|\]|\}|\d|true|false|null)\s*$', cur_stripped, flags=re.IGNORECASE)
                ):
                    cur = cur + ","
            out.append(cur)
        repaired = "\n".join(out)

    repaired = _insert_missing_commas_outside_strings(repaired)
    return repaired


def _strip_json_comments(text):
    """Remove // and /* */ comments outside JSON strings."""
    out = []
    in_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == "/" and nxt == "/":
            i += 2
            while i < n and text[i] not in ("\n", "\r"):
                i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2 if i + 1 <= n else 1
            continue

        out.append(ch)
        if ch == '"':
            in_string = True
        i += 1

    return "".join(out)


def _insert_missing_commas_outside_strings(text):
    """Insert commas between adjacent JSON values/keys when LLM dropped delimiters."""

    out = []
    in_string = False
    escape = False
    prev_sig = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
                prev_sig = '"'
            i += 1
            continue

        if ch == '"':
            if prev_sig and prev_sig not in "{[:,":  # value ended, but next token starts
                out.append(",")
            out.append(ch)
            in_string = True
            i += 1
            continue

        if ch in "{[":
            if prev_sig and prev_sig not in "{[:,":  # missing comma in arrays/objects
                out.append(",")
            out.append(ch)
            prev_sig = ch
            i += 1
            continue

        out.append(ch)
        if not ch.isspace():
            if ch in "-0123456789tfn":
                # Handle adjacent primitive values followed by key/value starts.
                prev_sig = ch
            else:
                prev_sig = ch
        i += 1

    # Fix missing commas before next object key in tight same-line format:
    # {"a":1 "b":2} -> {"a":1, "b":2}
    return re.sub(r'("|\]|\}|\d)\s+("([^"\\]|\\.)*"\s*:)', r'\1, \2', "".join(out))


def _parse_with_python_literal(text):
    """Fallback parser for near-JSON payloads with Python-compatible literals."""
    py_text = re.sub(r"\btrue\b", "True", text, flags=re.IGNORECASE)
    py_text = re.sub(r"\bfalse\b", "False", py_text, flags=re.IGNORECASE)
    py_text = re.sub(r"\bnull\b", "None", py_text, flags=re.IGNORECASE)
    value = ast.literal_eval(py_text)
    if not isinstance(value, (dict, list)):
        raise ValueError("top-level is not object/array")
    return value


def _parse_llm_json(raw_text, label="LLM"):
    text = _strip_code_fences(raw_text)
    block = _extract_json_block(text)
    attempts = [("raw", block), ("repaired", _repair_common_json_issues(block))]
    for _, candidate in attempts:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
        except Exception:
            continue

    # Fallback: near-JSON that is parseable as Python literal.
    for _, candidate in attempts:
        try:
            return _parse_with_python_literal(candidate)
        except Exception:
            continue

    # Build final error diagnostics from repaired payload.
    final_text = attempts[-1][1]
    try:
        json.loads(final_text)
    except json.JSONDecodeError as err:
        snippet_start = max(0, err.pos - 120)
        snippet_end = min(len(final_text), err.pos + 120)
        snippet = final_text[snippet_start:snippet_end].replace("\n", "\\n")
        raise RuntimeError(
            f"{label} JSON 解析失败: {err.msg} (line {err.lineno}, col {err.colno}); 附近内容: {snippet}"
        ) from err
    raise RuntimeError(f"{label} JSON 解析失败: 未知结构错误")


def _safe_user_address(raw_address):
    """Return the configured user address from soul.md."""
    return safe_user_address(raw_address)


def _sanitize_user_address_in_text(text, _raw_address=None, *,
                                   user_label=None, miru_name="Miru"):
    """Normalize soul.md prose for prompts addressed directly to Miru."""
    return normalize_character_section(
        text, user_label=user_label, miru_name=miru_name)


def _get_ai_runtime_or_raise(tier: str = "chat"):
    """Resolve a tier's runtime config or raise a clear error."""
    cfg = ai_config.get_tier_config(tier)
    tier_label = ai_config.TIER_LABELS.get(tier, tier)
    if not cfg["api_key"]:
        raise RuntimeError(
            f"Model configuration incomplete: {tier_label} tier is missing an API Key. "
            "Please fill it in the Model settings page in Sora."
        )
    if not cfg["host"]:
        raise RuntimeError(
            f"Model configuration incomplete: {tier_label} tier is missing a service URL. "
            "Please fill it in the Model settings page in Sora."
        )
    if not cfg["model"]:
        raise RuntimeError(
            f"Model configuration incomplete: {tier_label} tier is missing a model name. "
            "Please fill it in the Model settings page in Sora."
        )
    return cfg


def _get_chat_model():
    return _get_ai_runtime_or_raise("chat")["model"]


def _format_ai_call_error(exc, host, model):
    msg = str(exc) or exc.__class__.__name__
    lower = msg.lower()
    if "hostname mismatch" in lower or "certificate verify failed" in lower:
        msg += "; certificate/domain mismatch, please check Host settings under Settings > AI"
    elif "connection error" in lower:
        msg += "; please check network, proxy, or Host configuration"
    return f"{msg} (host={host}, model={model})"


# ---------------------------------------------------------------------------
# Retry utility for all API calls
# ---------------------------------------------------------------------------

def _unwrap_cause(exc):
    """Walk __cause__ chain to find the original exception."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        cause = getattr(exc, "__cause__", None)
        if cause is None:
            return exc
        exc = cause
    return exc


def _is_retryable_error(exc):
    """Determine if an exception is transient and safe to retry.

    Works with both Anthropic and OpenAI SDK exceptions.
    """
    candidates = [exc]
    root = _unwrap_cause(exc)
    if root is not exc:
        candidates.append(root)

    for e in candidates:
        # Upstream proxy transient auth errors (e.g. Google OAuth token refresh)
        # are returned as 400 with "invalid_grant" — safe to retry.
        err_msg = str(e).lower()
        if "invalid_grant" in err_msg:
            return True

        # Check by status code (works for both SDKs)
        status = getattr(e, "status_code", None) or getattr(e, "status", None)
        if status is not None:
            if status in (429, 500, 502, 503, 504):
                return True
            if status in (400, 401, 403, 404):
                return False

        # Check by class name string (avoid hard import)
        cls_name = type(e).__name__
        if cls_name in ("RateLimitError", "InternalServerError", "APIConnectionError",
                        "APITimeoutError", "APIError"):
            return True
        if cls_name in ("AuthenticationError", "PermissionDeniedError",
                        "BadRequestError", "NotFoundError"):
            return False

        # OpenAI timeout / connection errors
        if isinstance(e, (ConnectionError, TimeoutError, OSError)):
            return True

    # RuntimeError from empty response or JSON parse failure — retry
    if isinstance(exc, RuntimeError):
        msg = str(exc).lower()
        if (
            "model configuration incomplete" in msg
            or "api key" in msg
            or "not set" in msg
        ):
            return False
        return True

    return False


def _get_retry_after(exc):
    """Extract Retry-After seconds from a RateLimitError, or None.

    Checks __cause__ chain since the RateLimitError may be wrapped.
    """
    # Check both the exception and its root cause for retry-after header
    for e in [exc, _unwrap_cause(exc)]:
        response = getattr(e, "response", None)
        if response is None:
            continue
        header = getattr(response, "headers", {}).get("retry-after")
        if header:
            try:
                return float(header)
            except (ValueError, TypeError):
                pass
    return None


def _api_call_with_retry(fn, max_retries=3, base_delay=2.0, label="API"):
    """Execute fn() with exponential backoff retry on transient errors.

    Retries on: 429, 5xx, connection errors, timeouts, empty responses,
                JSON parse failures (RuntimeError).
    Does NOT retry on: 401, 403, 400, 404, config errors.

    Args:
        fn: Callable that performs the API call and returns the result.
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Base delay in seconds before first retry (default 2.0).
        label: Label for log messages.
    Returns: Result of fn().
    Raises: The last exception if all retries are exhausted.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not _is_retryable_error(exc) or attempt == max_retries:
                raise

            # Calculate delay: exponential backoff + jitter
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)

            # Respect Retry-After header for rate limit errors
            retry_after = _get_retry_after(exc)
            if retry_after is not None:
                delay = max(delay, retry_after)

            # Cap delay at 60 seconds
            delay = min(delay, 60.0)

            print(f"[Retry] {label} attempt {attempt + 1}/{max_retries} failed: "
                  f"{exc.__class__.__name__}: {exc}. Retrying in {delay:.1f}s...")
            time.sleep(delay)

    raise last_exc  # Should not reach here, but safety net


# ---------------------------------------------------------------------------
# Core API call helpers
# ---------------------------------------------------------------------------

def _get_client(runtime=None, tier: str = "chat"):
    """Return (OpenAI client, "openai") for the given tier.

    Backward-compat: `runtime` arg ignored if passed (legacy callers).
    Always returns ("openai") as the second element so old call sites
    that destructure `client, provider = _get_client(...)` still work.

    The OpenAI client is cached per-tier inside ai_config so we don't
    rebuild httpx pools on every LLM call.
    """
    return ai_config.get_tier_client(tier), "openai"


def _vendor_extra_body(model: str, host: str = "",
                       reasoning: bool = False,
                       reasoning_budget: int = 16000) -> dict:
    """Return vendor-specific extra_body to pass to chat.completions.create.

    Several modern LLMs default to *reasoning* mode (DeepSeek V4, Qwen3.5,
    GPT-5, etc.). For most callers we keep reasoning OFF so the output goes
    straight to the answer and doesn't burn tokens on internal monologue.

    For callers that benefit from reasoning (Sleep Agent v3 Slot Writer /
    Persona Writer — complex multi-fact decisions), pass ``reasoning=True``
    to flip the relevant vendor flag.

    Coverage (per host match):
    - OpenRouter (openrouter.ai/api): ``reasoning: {enabled: bool, max_tokens?}``
      — works for ALL reasoning models routed through OpenRouter.
    - DeepSeek direct (api.deepseek.com or *.deepseek.com only):
      ``thinking: {type: "enabled"|"disabled"}``.
    - Other providers (Anthropic, OpenAI, ...): no flag needed; their
      defaults are sensible enough for now. Extend here when concrete needs
      surface (don't speculate-add vendor branches).

    Returns {} for unknown hosts/models so we never send a field the
    provider would reject.

    Args:
        model: model id (e.g. "deepseek-v4-pro", "qwen/qwen3.5-9b")
        host: API host (e.g. "api.deepseek.com", "openrouter.ai/api")
        reasoning: True to enable reasoning, False (default) to disable.
        reasoning_budget: max tokens reserved for reasoning (OpenRouter only,
                          DeepSeek's flag is on/off, doesn't take budget).
    """
    h = (host or "").lower()
    host_name = h.split("/", 1)[0]
    is_openrouter = host_name == "openrouter.ai"
    is_deepseek_direct = host_name == "api.deepseek.com" or host_name.endswith(".deepseek.com")

    if reasoning:
        # Explicitly enable reasoning.
        if is_openrouter:
            return {"reasoning": {"enabled": True, "max_tokens": reasoning_budget}}
        if is_deepseek_direct:
            return {"thinking": {"type": "enabled"}}
        # Unknown provider — let its default behavior apply.
        return {}

    # Default path: disable reasoning so small max_tokens caps don't
    # produce empty content.
    if is_openrouter:
        return {"reasoning": {"enabled": False}}
    if is_deepseek_direct:
        return {"thinking": {"type": "disabled"}}
    return {}


def _extract_text_from_response(response, provider="openai"):
    """Extract text content from an OpenAI-compatible response.

    `provider` arg kept for backward compat; always treated as openai.
    """
    if isinstance(response, str):
        raise RuntimeError(
            "API returned HTML/text instead of JSON. Check your AI Host setting."
        )
    choice = response.choices[0] if getattr(response, "choices", None) else None
    if choice and choice.message and choice.message.content:
        return choice.message.content.strip()
    return ""


def _call_llm_text(system_prompt, user_text, temperature=0.3, max_tokens=None,
                   tier: str = "memory", reasoning: bool = False,
                   reasoning_budget: int = 16000,
                   call_label: str = "llm_text"):
    """Call LLM and return raw text response.

    Args:
        tier: "vision" / "chat" / "memory" — which configured backend to use.
              Defaults to "memory" since most non-chat callers are post-chat
              memory work.
        max_tokens: defaults to the tier's configured max_tokens if None.
        reasoning: if True, request reasoning mode (DeepSeek thinking /
                   OpenRouter reasoning). Default False keeps reasoning off
                   so outputs come straight to the point.
        reasoning_budget: max tokens reserved for reasoning trace
                          (OpenRouter only; ignored on DeepSeek direct).
    """
    runtime = _get_ai_runtime_or_raise(tier)
    model = runtime["model"]
    host = runtime["host"]
    max_tokens = ai_config.resolve_max_tokens(tier, max_tokens)
    client = ai_config.get_tier_client(tier)

    extra_body = _vendor_extra_body(model, host, reasoning=reasoning,
                                     reasoning_budget=reasoning_budget)

    def _do_call():
        try:
            response = client.chat.completions.create(
                model=model, max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                temperature=temperature,
                extra_body=extra_body,
            )
        except Exception as exc:
            raise RuntimeError(_format_ai_call_error(exc, host, model)) from exc

        _log_llm_usage(
            tier, model, response,
            call_label=call_label or "llm_text",
            reasoning_enabled=reasoning,
            reasoning_budget=reasoning_budget if reasoning else 0,
            max_tokens=max_tokens,
        )
        text = _extract_text_from_response(response)
        if not text:
            raise RuntimeError(f"Empty LLM response (model={model})")
        return text

    return _api_call_with_retry(_do_call, label=f"LLM[{tier}]({model})")


def _call_llm_json(system_prompt, user_text, temperature=0.3, max_tokens=None,
                   tier: str = "memory", reasoning: bool = False,
                   reasoning_budget: int = 16000,
                   call_label: str = "llm_json"):
    """Call LLM and return parsed JSON. Defaults to memory tier.

    Args:
        reasoning: if True, enable reasoning mode for the underlying call.
                   Sleep Agent v3 (Slot Writer / Persona Writer) sets this
                   True; legacy callers leave it False (default).
    """
    json_system = system_prompt + "\n\n【输出格式】你必须只输出合法 JSON，不要输出任何其他文本、解释或 markdown 格式。"
    raw = _call_llm_text(json_system, user_text, temperature, max_tokens,
                          tier=tier, reasoning=reasoning,
                          reasoning_budget=reasoning_budget,
                          call_label=call_label)
    return _parse_llm_json(raw, label=f"LLM[{tier}]")


def _call_llm_multimodal_json(system_prompt, parts, temperature=0.3,
                               max_tokens=None, tier: str = "vision",
                               reasoning: bool = False,
                               reasoning_budget: int = 16000):
    """Call LLM with multimodal content (text + images) and return parsed JSON.

    Defaults to vision tier (cheaper VLM). Pass tier="chat" to use the
    capable multimodal model for the main conversation path.

    reasoning: same semantics as _call_llm_json.
    """
    runtime = _get_ai_runtime_or_raise(tier)
    model = runtime["model"]
    host = runtime["host"]
    max_tokens = ai_config.resolve_max_tokens(tier, max_tokens)
    client = ai_config.get_tier_client(tier)

    json_system = system_prompt + "\n\n【输出格式】你必须只输出合法 JSON，不要输出任何其他文本、解释或 markdown 格式。"
    extra_body = _vendor_extra_body(model, host, reasoning=reasoning,
                                     reasoning_budget=reasoning_budget)

    def _do_call():
        try:
            content = []
            for part in parts:
                if "inlineData" in part:
                    inline = part["inlineData"]
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{inline['mimeType']};base64,{inline['data']}"},
                    })
                elif "text" in part:
                    content.append({"type": "text", "text": part["text"]})
            response = client.chat.completions.create(
                model=model, max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": json_system},
                    {"role": "user", "content": content},
                ],
                temperature=temperature,
                extra_body=extra_body,
            )
        except Exception as exc:
            raise RuntimeError(_format_ai_call_error(exc, host, model)) from exc

        _log_llm_usage(
            tier, model, response,
            call_label="llm_multimodal_json",
            reasoning_enabled=reasoning,
            reasoning_budget=reasoning_budget if reasoning else 0,
            max_tokens=max_tokens,
        )
        text = _extract_text_from_response(response)
        if not text:
            raise RuntimeError(f"Empty LLM response (model={model})")
        return _parse_llm_json(text, label=f"LLM-multimodal[{tier}]")

    return _api_call_with_retry(_do_call, label=f"LLM-multimodal[{tier}]({model})")


def _call_retrieval_llm(system_prompt, user_text, temperature=0.1,
                        max_tokens=None, tier: str = "memory",
                        call_label: str = "retrieval_llm"):
    """Call LLM for retrieval tasks. Returns parsed JSON. Defaults to memory tier."""
    return _call_llm_json(
        system_prompt, user_text, temperature, max_tokens,
        tier=tier, call_label=call_label,
    )


# ---------------------------------------------------------------------------
# Memory Pre-Retrieval — enrich context BEFORE agent loop
# ---------------------------------------------------------------------------

_CHAT_PREFLIGHT_PROMPT = """You are Miru's Memory Retriever before the main chat.

You are not the main agent.
You do not answer for the user, call tools, write memory, or provide emotional comfort.
Your only task: select the memory files the main agent should pre-load before answering the current user message, based on the global long-term memory index memory/index.md.

The main agent's model tier is fixed to 'pro' by code; do not judge between 'fast' / 'pro' / 'reasoning' and do not output model suggestions.

【Long-Term Memory Retrieval Scope】

Core Memory (human / persona) is always in the main agent's context and does not need retrieval.

You received memory/index.md as the "Global Long-Term Memory Index", not just for one directory.
Retrieval scope includes:
- Slot memory: `main.md` files under projects/, people/, topics/, self/
- Long-term memory: markdown files in commitments/, journal/, patterns/, etc.
- Legacy memory: direct markdown files like `people/name.md` or `projects/name.md`

Any file in the index relevant to the user's message can be added to 'files'.

Paths in the index may appear as:
- Backticks: `projects/papers_2026/main.md`
- Markdown links: [papers](projects/papers_2026/main.md)

Your 'files' output must use the exact relative paths from the index.

【Retrieval Strategy】

1. Look at the title + summary for each index entry to find semantically relevant files.
   - User says "feeling stressed" -> match files in self/ or patterns/ about routine, stress, health
   - User says "How is Xiao Zhang?" -> match the corresponding file in people/
   - User says "the paper" -> match the corresponding project file in projects/
   - User says "my task" -> match commitments/active.md
2. Extract 1-2 keywords if necessary to supplement information not covered by the index summary.
3. Max 5 files, priority: explicitly mentioned > semantically relevant > recently active.
4. Max 2 keywords, only if index description is clearly insufficient.
5. For casual chat like "mm", "haha", "morning", "goodnight", `need_retrieval=false` is acceptable.
6. If the user asks about specific history, people, projects, commitments, papers, bugs, travel, relationships, etc., `need_retrieval=true` is typically required.
7. Err on the side of over-retrieval; do not miss context the main agent must have.

【Output JSON】

You must output valid JSON only. No markdown, no explanation.

{
  "need_retrieval": true,
  "files": ["projects/example/main.md"],
  "keywords": ["keyword"],
  "confidence": 0.82,
  "retrieval_reason": "User mentioned specific project, need to load corresponding slot"
}

Field requirements:
- need_retrieval: boolean
- files: string[] (max 5, must use real paths from index)
- keywords: string[] (max 2)
- confidence: 0 to 1
- retrieval_reason: 20-80 chars, explain why retrieval is needed/not needed"""

# Backward-compatible name for older tests/imports. The prompt now performs
# memory pre-retrieval only; main-agent model routing is fixed in core.py.
_MEMORY_RETRIEVAL_PROMPT = _CHAT_PREFLIGHT_PROMPT


_PREFLIGHT_AGENT_MODES = {"fast", "v4_pro", "v4_pro_reasoning"}
_PREFLIGHT_COMPLEXITIES = {"simple", "normal", "hard"}
_PREFLIGHT_TOOL_LIKELIHOODS = {"none", "possible", "likely"}
_PREFLIGHT_REASONING_NEEDS = {"none", "low", "high"}
_PREFLIGHT_LATENCY_PREFS = {"fast", "normal", "quality"}


def _extract_index_file_paths(index_content: str) -> set[str]:
    """Return relative memory paths explicitly listed in index.md.

    Supports both the v3 slot index style (backticked paths) and old markdown
    links like ``[foo](people/foo.md)``.
    """
    if not index_content:
        return set()
    paths = set()
    for pattern in (r"`([^`]+\.md)`", r"\]\(([^)]+\.md)\)"):
        for raw in re.findall(pattern, index_content):
            p = str(raw or "").strip()
            if p and ".." not in p and not p.startswith("/"):
                paths.add(p)
    return paths


def _coerce_bool(value, default=True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "yes", "1"}:
            return True
        if v in {"false", "no", "0"}:
            return False
    return default


def _coerce_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_chat_preflight(raw) -> dict:
    """Normalize/validate memory preflight JSON into a safe dict.

    Legacy routing fields are preserved with fixed defaults for old callers,
    but live main-agent model selection ignores them.
    """
    if not isinstance(raw, dict):
        raw = {}

    mode = raw.get("agent_mode")
    if mode not in _PREFLIGHT_AGENT_MODES:
        mode = "v4_pro"

    complexity = raw.get("complexity")
    if complexity not in _PREFLIGHT_COMPLEXITIES:
        complexity = "normal"

    tool_likelihood = raw.get("tool_likelihood")
    if tool_likelihood not in _PREFLIGHT_TOOL_LIKELIHOODS:
        tool_likelihood = "possible"

    reasoning_need = raw.get("reasoning_need")
    if reasoning_need not in _PREFLIGHT_REASONING_NEEDS:
        reasoning_need = "low"

    latency_preference = raw.get("latency_preference")
    if latency_preference not in _PREFLIGHT_LATENCY_PREFS:
        latency_preference = "normal"

    confidence = max(0.0, min(1.0, _coerce_float(raw.get("confidence"), 0.0)))

    files = []
    for fpath in raw.get("files", []) if isinstance(raw.get("files"), list) else []:
        if not isinstance(fpath, str):
            continue
        fpath = fpath.strip()
        if fpath and ".." not in fpath and not fpath.startswith("/") and fpath.endswith(".md"):
            files.append(fpath)
        if len(files) >= 5:
            break

    keywords = []
    for kw in raw.get("keywords", []) if isinstance(raw.get("keywords"), list) else []:
        if not isinstance(kw, str):
            continue
        kw = kw.strip()
        if kw:
            keywords.append(kw[:40])
        if len(keywords) >= 2:
            break

    return {
        "need_retrieval": _coerce_bool(raw.get("need_retrieval"), True),
        "files": files,
        "keywords": keywords,
        "agent_mode": mode,
        "confidence": confidence,
        "complexity": complexity,
        "tool_likelihood": tool_likelihood,
        "reasoning_need": reasoning_need,
        "latency_preference": latency_preference,
        "routing_reason": str(raw.get("retrieval_reason") or raw.get("routing_reason") or "")[:120],
        "retrieval_reason": str(raw.get("retrieval_reason") or raw.get("routing_reason") or "")[:120],
    }


def _fallback_chat_preflight(memory_context: str = "", reason: str = "") -> dict:
    return {
        "need_retrieval": bool(memory_context),
        "files": [],
        "keywords": [],
        "agent_mode": "v4_pro",
        "confidence": 0.0,
        "complexity": "normal",
        "tool_likelihood": "possible",
        "reasoning_need": "low",
        "latency_preference": "normal",
        "routing_reason": reason or "memory preflight 失败或输出不可用",
        "retrieval_reason": reason or "memory preflight 失败或输出不可用",
        "memory_context": memory_context,
        "raw": {},
        "preflight_error": reason,
    }


# Legacy helper kept for old review scripts/tests. Production delivery no
# longer calls this; proactive main agent is fixed to chat/v4_pro/no reasoning.
_PROACTIVE_RESOURCE_PLANNER_PROMPT = """You are Sora's Fast LLM Resource Planner before speaking proactively.

You are not the main agent, do not write the final message, do not call tools, and do not write memory.
The AttentionEngine has already decided that Sora should speak proactively; you **cannot** decide send/defer/drop.

Your sole tasks:
1. Determine which model resource the proactive main agent should use.
2. Determine whether read-only tools or pre-loaded long-term memories are needed.
3. Provide the main agent with a short context_brief to help it avoid hallucination, repetition, or sounding like a system alert.

First Principles:
- Proactive messages should sound like a girl who genuinely cares about the user and wants to get close, speaking naturally rather than a notification system.
- Cheaper resources are better, but never sacrifice quality for cost if it makes proactive messages sound mechanical, misunderstand the user, or fabricate facts.
- Reasoning is expensive and slow; enable it only when genuinely difficult. Most proactive messages do not need reasoning.
- Tool capabilities are used to verify facts and avoid fabrication, not to make Sora look like she's monitoring the user.
- When unsure, choose v4_pro with reasoning disabled.

【Available Models】

1. fast
Fastest and cheapest.
Suitable for: Extremely short, light, tool-free companionship without needing memory details.
Forbidden: Needing memory lookup, screen observation, DDL/project/debugging/complex emotional evaluation, or any tool calls.

2. v4_pro
Default mode.
Suitable for: Normal proactive messages, maintaining a stable tone, needing read-only tools, reading long-term memory, or confirming context.
Choose this when unsure.

3. v4_pro_reasoning
Slowest and most expensive.
Suitable only for rare cases: multi-step debugging, architectural trade-offs, complex project blockages, user explicitly not rushing but needing high-quality help, or when `speak_intent` explicitly requires the main agent to use tools to understand complex context before speaking.
Do not enable reasoning for ordinary care, routine DDL reminders, or standard emotional companionship.

【Tool Policy】

- none: No tools provided. Suitable for fast or light companionship requiring no factual confirmation.
- allow_readonly: Allow the main agent to use `archival_memory_search` and `look_at_screen`. Suitable when confirming projects, DDLs, recent context, or screen status to avoid hallucinating from the index.
- allow_all: Do not choose by default. Proactive openings without explicit user request should not write commitments or modify state.

【Long-term Memory Retrieval Scope】

Core Memory is already permanently in the main agent's context and does not need retrieval.
You receive the global long-term memory index (`memory/index.md`), covering:
- Slot memories: `<slot_id>/main.md` under projects/, people/, topics/, self/
- Non-slot long-term memories: markdown files under commitments/, journal/, patterns/, etc.
- Legacy memories: e.g., `people/name.md`, `projects/name.md`

`memory_files` in your output must be relative `.md` paths that actually appear in the index.
Fill only when the proactive main agent needs specific facts; up to 5 files.

【Output JSON】

Output valid JSON only, no markdown, no explanations:

{
  "model_mode": "v4_pro",
  "confidence": 0.84,
  "complexity": "normal",
  "reasoning_need": "low",
  "tool_policy": "allow_readonly",
  "memory_files": ["projects/example/main.md"],
  "keywords": ["keyword"],
  "context_brief": "Short context brief for the proactive main agent, emphasizing naturalness and no fabrication",
  "routing_reason": "Reason for choosing this model and tools, 20-80 chars"
}

Field Constraints:
- model_mode: Must be "fast", "v4_pro", or "v4_pro_reasoning"
- confidence: 0 to 1; below 0.65 means you are insufficiently confident, and code defaults to v4_pro with no reasoning
- complexity: Must be "simple", "normal", or "hard"
- reasoning_need: Must be "none", "low", or "high"
- tool_policy: Must be "none", "allow_readonly", or "allow_all"
- memory_files: string[], up to 5 paths, must be valid `.md` paths from the index
- keywords: string[], up to 2 items
- context_brief: 40-500 characters
- Do not output decision / send_now / defer / drop"""

_PROACTIVE_RESOURCE_COMPLEXITIES = {"simple", "normal", "hard"}
_PROACTIVE_RESOURCE_REASONING = {"none", "low", "high"}
_PROACTIVE_TOOL_POLICIES = {"none", "allow_readonly", "allow_all"}


def _normalize_proactive_resource_plan(raw) -> dict:
    if not isinstance(raw, dict):
        raw = {}

    mode = raw.get("model_mode")
    if mode not in _PREFLIGHT_AGENT_MODES:
        mode = "v4_pro"

    confidence = max(0.0, min(1.0, _coerce_float(raw.get("confidence"), 0.0)))

    complexity = raw.get("complexity")
    if complexity not in _PROACTIVE_RESOURCE_COMPLEXITIES:
        complexity = "normal"

    reasoning_need = raw.get("reasoning_need")
    if reasoning_need not in _PROACTIVE_RESOURCE_REASONING:
        reasoning_need = "low"

    tool_policy = raw.get("tool_policy")
    if tool_policy not in _PROACTIVE_TOOL_POLICIES:
        tool_policy = "allow_readonly"

    files = []
    for fpath in raw.get("memory_files", []) if isinstance(raw.get("memory_files"), list) else []:
        if not isinstance(fpath, str):
            continue
        fpath = fpath.strip()
        if fpath and ".." not in fpath and not fpath.startswith("/") and fpath.endswith(".md"):
            files.append(fpath)
        if len(files) >= 5:
            break

    keywords = []
    for kw in raw.get("keywords", []) if isinstance(raw.get("keywords"), list) else []:
        if not isinstance(kw, str):
            continue
        kw = kw.strip()
        if kw:
            keywords.append(kw[:40])
        if len(keywords) >= 2:
            break

    return {
        "model_mode": mode,
        "confidence": confidence,
        "complexity": complexity,
        "reasoning_need": reasoning_need,
        "tool_policy": tool_policy,
        "memory_files": files,
        "keywords": keywords,
        "context_brief": str(raw.get("context_brief") or "")[:500],
        "routing_reason": str(raw.get("routing_reason") or "")[:160],
        "raw": raw,
    }


def _fallback_proactive_resource_plan(reason: str = "") -> dict:
    return {
        "model_mode": "v4_pro",
        "confidence": 0.0,
        "complexity": "normal",
        "reasoning_need": "low",
        "tool_policy": "allow_readonly",
        "memory_files": [],
        "keywords": [],
        "context_brief": "资源规划不可用；使用默认稳定模式，让主 agent 根据现有上下文自然生成主动消息。",
        "routing_reason": reason or "resource planner failed, default v4_pro no reasoning",
        "raw": {},
        "planner_error": reason,
    }


def call_proactive_resource_planner(delivery_context: str,
                                    index_content: str | None = None) -> dict:
    """Legacy resource planner for proactive main-agent delivery.

    Production `deliver_attention_intent_once()` no longer calls this helper;
    it is kept so old diagnostics/tests can still render the retired prompt.
    """
    import memory

    if not delivery_context or not delivery_context.strip():
        return _fallback_proactive_resource_plan("empty delivery context")

    if index_content is None:
        try:
            index_content = memory.read_index()
        except Exception:
            index_content = ""

    valid_index_paths = _extract_index_file_paths(index_content)
    user_text = (
        f"【记忆索引】\n{index_content}\n\n"
        f"【Attention Delivery Context】\n{delivery_context}"
    )

    try:
        raw = _call_retrieval_llm(
            _PROACTIVE_RESOURCE_PLANNER_PROMPT,
            user_text,
            temperature=0.05,
            max_tokens=16000,
            call_label="ProactiveResourcePlanner",
        )
    except Exception as e:
        print(f"[ProactiveResourcePlanner] LLM call failed: {e}")
        return _fallback_proactive_resource_plan(str(e))

    result = _normalize_proactive_resource_plan(raw)
    if valid_index_paths:
        result["memory_files"] = [
            fpath for fpath in result.get("memory_files", [])
            if fpath in valid_index_paths
        ][:5]
    return result


_PROACTIVE_DELIVERY_PREFLIGHT_PROMPT = """You are Sora's Fast LLM Gatekeeper before Attention Delivery.

You are not the main agent, do not write the final message, do not call tools, and do not write memory.
Your task is to judge whether, after Sora's AttentionEngine has generated a , this intent should actually be passed to the main agent to generate a proactive message.

First Principles:
- The user did not ask you directly, so the default is not to disturb.
- A proactive opening must simultaneously satisfy: helpful or warm, appropriate timing, non-repetitive, and not sounding like a system reminder.
- If the user recently failed to respond to Sora's proactive message, normally defer.
- If it's merely restating "seeing what the user is doing," normally do not speak.
- Only when there are clear difficulties, obvious emotional changes, important progress, or genuine approaching/overdue DDLs should you consider .
-  is not only for problem-solving: when cadence is quiet, there are no unresponded proactive messages, the intent is specific and low-burden, and it conveys Sora's gentle presence,  is also permitted.
- When unsure, defer; when expired or repetitive, drop.
- Proactive messages must feel like natural care; do not mention systems, logs, AttentionEngine, preflight, screenshot analysis, or "detected."
- Do not ask questions requiring user replies just for the sake of talking; unless genuinely helpful, use a short touch of companionship.

Model Selection:
- fast: Suitable only for very light, short, tool-free companionship without long-term memory checks.
- v4_pro: Default proactive message generation mode, stable, capable of using context.
- v4_pro_reasoning: Extremely rare, used only for multi-step debugging / architectural trade-offs / user explicitly not rushing but needing high quality.

Tool Policy:
- none: Default, tools not allowed.
- allow_readonly: Allow reading memory or looking at screen only, suitable when confirming context without writing data.
- allow_all: Extremely rare, considered only when the proactive message must handle DDL/completion status.

Output must be valid JSON, no markdown, no explanations:
{
  "decision": "send_now",
  "confidence": 0.82,
  "reason": "Why it is or isn't worth speaking now, 40-100 chars",
  "model_mode": "v4_pro",
  "tool_policy": "none",
  "cooldown_seconds": 1800,
  "memory_files": [],
  "keywords": [],
  "delivery_brief": {
    "goal": "What this proactive message aims to achieve",
    "must_include": [],
    "must_avoid": [],
    "tone": "Short, light, like Sora, not a reminder",
    "context_summary": "Full context summary for the main agent"
  }
}

Field Constraints:
- decision: "send_now" | "defer" | "drop"
- confidence: 0 to 1; below 0.7 means you are unsure
- model_mode: "fast" | "v4_pro" | "v4_pro_reasoning"
- tool_policy: "none" | "allow_readonly" | "allow_all"
- cooldown_seconds: 300 to 7200
- memory_files: string[], up to 5 paths, must be valid `.md` paths from the index
- keywords: string[], up to 2 items
- delivery_brief.goal/tone/context_summary must have content
- must_include/must_avoid: string[]"""


_PROACTIVE_DECISIONS = {"send_now", "defer", "drop"}


def _normalize_proactive_delivery_preflight(raw) -> dict:
    if not isinstance(raw, dict):
        raw = {}

    decision = raw.get("decision")
    if decision not in _PROACTIVE_DECISIONS:
        decision = "defer"

    confidence = max(0.0, min(1.0, _coerce_float(raw.get("confidence"), 0.0)))
    mode = raw.get("model_mode")
    if mode not in _PREFLIGHT_AGENT_MODES:
        mode = "v4_pro"

    tool_policy = raw.get("tool_policy")
    if tool_policy not in _PROACTIVE_TOOL_POLICIES:
        tool_policy = "none"

    cooldown_seconds = int(max(300, min(7200, _coerce_float(raw.get("cooldown_seconds"), 1800))))

    files = []
    for fpath in raw.get("memory_files", []) if isinstance(raw.get("memory_files"), list) else []:
        if not isinstance(fpath, str):
            continue
        fpath = fpath.strip()
        if fpath and ".." not in fpath and not fpath.startswith("/") and fpath.endswith(".md"):
            files.append(fpath)
        if len(files) >= 5:
            break

    keywords = []
    for kw in raw.get("keywords", []) if isinstance(raw.get("keywords"), list) else []:
        if not isinstance(kw, str):
            continue
        kw = kw.strip()
        if kw:
            keywords.append(kw[:40])
        if len(keywords) >= 2:
            break

    brief = raw.get("delivery_brief") if isinstance(raw.get("delivery_brief"), dict) else {}
    must_include = [
        str(x).strip()[:120] for x in brief.get("must_include", [])
        if isinstance(x, str) and x.strip()
    ][:6] if isinstance(brief.get("must_include"), list) else []
    must_avoid = [
        str(x).strip()[:120] for x in brief.get("must_avoid", [])
        if isinstance(x, str) and x.strip()
    ][:6] if isinstance(brief.get("must_avoid"), list) else []

    return {
        "decision": decision,
        "confidence": confidence,
        "reason": str(raw.get("reason") or "")[:200],
        "model_mode": mode,
        "tool_policy": tool_policy,
        "cooldown_seconds": cooldown_seconds,
        "memory_files": files,
        "keywords": keywords,
        "delivery_brief": {
            "goal": str(brief.get("goal") or "")[:240],
            "must_include": must_include,
            "must_avoid": must_avoid,
            "tone": str(brief.get("tone") or "")[:160],
            "context_summary": str(brief.get("context_summary") or "")[:500],
        },
        "raw": raw,
    }


def _fallback_proactive_delivery_preflight(reason: str = "") -> dict:
    return {
        "decision": "defer",
        "confidence": 0.0,
        "reason": reason or "delivery preflight failed, default defer",
        "model_mode": "v4_pro",
        "tool_policy": "none",
        "cooldown_seconds": 1800,
        "memory_files": [],
        "keywords": [],
        "delivery_brief": {
            "goal": "暂不主动开口",
            "must_include": [],
            "must_avoid": ["不要打扰用户"],
            "tone": "沉默观察",
            "context_summary": "",
        },
        "raw": {},
        "preflight_error": reason,
    }


def call_proactive_delivery_preflight(delivery_context: str,
                                      index_content: str | None = None) -> dict:
    """Judge whether a pending Attention speak_intent should be delivered.

    This is a cheap fast-LLM gate. It does not send anything; callers must
    apply hard rules and, if accepted, invoke the proactive main-agent wrapper.
    """
    import memory

    if not delivery_context or not delivery_context.strip():
        return _fallback_proactive_delivery_preflight("empty delivery context")

    if index_content is None:
        try:
            index_content = memory.read_index()
        except Exception:
            index_content = ""

    valid_index_paths = _extract_index_file_paths(index_content)
    user_text = f"【记忆索引】\n{index_content}\n\n【Attention Delivery Context】\n{delivery_context}"

    try:
        raw = _call_retrieval_llm(
            _PROACTIVE_DELIVERY_PREFLIGHT_PROMPT,
            user_text,
            temperature=0.05,
            max_tokens=16000,
            call_label="ProactiveDeliveryPreflightLegacy",
        )
    except Exception as e:
        print(f"[ProactiveDeliveryPreflight] LLM call failed: {e}")
        return _fallback_proactive_delivery_preflight(str(e))

    result = _normalize_proactive_delivery_preflight(raw)
    if valid_index_paths:
        result["memory_files"] = [
            fpath for fpath in result.get("memory_files", [])
            if fpath in valid_index_paths
        ][:5]
    return result


def call_chat_preflight(user_text, index_content=None, user_image_descs=None):
    """Pre-retrieve memory before calling the fixed pro main agent.

    Args:
        user_text: The user's current message text (may be empty if image-only).
        index_content: memory/index.md content (auto-loaded if None).
        user_image_descs: optional list of image *descriptions* (Chinese
            120-180 字 strings) for images attached to this user message.
            Generated upstream by vision.describe_image() so retrieval
            stays text-only — memory tier (DeepSeek V4-flash) doesn't
            support images.

    Returns:
        dict with selected memory files/keywords plus ``memory_context``.
        Legacy routing fields are present but ignored by core.py.
    """
    import memory

    if not (user_text and user_text.strip()) and not user_image_descs:
        return _fallback_chat_preflight(reason="empty user message")

    if index_content is None:
        try:
            index_content = memory.read_index()
        except Exception:
            index_content = ""

    valid_index_paths = _extract_index_file_paths(index_content)

    # Splice image descriptions inline so retrieval LLM sees what the user
    # sent without us needing to upload the image bytes themselves.
    msg_section = user_text or "(User sent an image only)"
    if user_image_descs:
        for d in user_image_descs[:3]:  # cap at 3 to keep token cost bounded
            d = (d or "").strip()
            if d:
                msg_section += f"\n[Image: {d}]"

    base_text = (
        f"【记忆索引】\n{index_content}\n\n"
        f"【用户消息】\n{msg_section}"
    )

    try:
        result = _call_retrieval_llm(
            _CHAT_PREFLIGHT_PROMPT,
            base_text,
            temperature=0.1, max_tokens=4000,
            call_label="ChatPreflight",
        )
    except Exception as e:
        print(f"[ChatPreflight] LLM call failed, falling back to keyword search: {e}")
        # Fallback: simple keyword search
        kw_query = user_text or "今天"
        results = memory.search(kw_query, max_results=3)
        return _fallback_chat_preflight(
            _format_search_results(results),
            reason=f"preflight LLM failed: {e}",
        )

    preflight = _normalize_chat_preflight(result)

    if not preflight.get("need_retrieval", True):
        preflight["memory_context"] = ""
        preflight["raw"] = result if isinstance(result, dict) else {}
        return preflight

    # Step 2: Read specified files (primary) + keyword search (supplementary)
    snippets = []
    loaded_paths = set()

    # Primary: direct file reads from LLM's index-based matching
    for fpath in preflight.get("files", [])[:5]:
        # If index.md listed paths, require the LLM to pick from that set.
        # Empty set means legacy/broken index; memory.read_file remains safe.
        if valid_index_paths and fpath not in valid_index_paths:
            continue
        content = memory.read_file(fpath)
        if content:
            if len(content) > 800:
                content = content[:800] + "..."
            snippets.append(f"[{fpath}]\n{content}")
            loaded_paths.add(fpath)

    # Supplementary: keyword search for files not in index
    for kw in preflight.get("keywords", [])[:2]:
        results = memory.search(kw, max_results=2)
        for r in results:
            fpath = r.get("path", "")
            if fpath in loaded_paths:
                continue
            content = memory.read_file(fpath)
            if content:
                if len(content) > 500:
                    content = content[:500] + "..."
                snippets.append(f"[{fpath}]\n{content}")
                loaded_paths.add(fpath)

    if snippets:
        preflight["memory_context"] = (
            "【Relevant Long-term Memories — cite naturally, do not say \"I checked\" or \"according to records\"】\n"
            + "\n\n".join(snippets[:5])
        )
    else:
        preflight["memory_context"] = ""
    preflight["raw"] = result if isinstance(result, dict) else {}
    return preflight


def call_memory_retrieval(user_text, index_content=None, user_image_descs=None):
    """Backward-compatible wrapper returning only formatted memory context."""
    result = call_chat_preflight(
        user_text,
        index_content=index_content,
        user_image_descs=user_image_descs,
    )
    if isinstance(result, dict):
        return result.get("memory_context", "")
    return result or ""


def _format_search_results(results):
    """Format memory search results as context text."""
    if not results:
        return ""
    import memory
    snippets = []
    for r in results[:3]:
        fpath = r.get("path", "")
        content = memory.read_file(fpath)
        if content:
            if len(content) > 500:
                content = content[:500] + "..."
            snippets.append(f"[{fpath}]\n{content}")
    if not snippets:
        return ""
    return ("【Relevant Long-term Memories — cite naturally, do not say \"I checked\" or \"according to records\"】\n"
            + "\n\n".join(snippets))



# _build_daily_review_prompt, call_daily_review, _build_morning_reminder_prompt,
# call_morning_reminder — removed. All proactive messages now go through call_chat_agent.


def _build_diary_reformat_prompt():
    """Build prompt to reformat a chat-style message into Miru's diary entry."""
    cfg = get_config()
    name = cfg.name
    user_label = resolve_user_entity_label()

    return f"""你是 {name}，在写自己的日记。你会收到一段你之前发给{user_label}的对话消息，请把它改写成日记体。

【改写要求】
- 从第一人称（{name}）的视角写，像在记录自己的感受和观察
- 书面但不正式——像真实的少女日记，有内心独白的感觉
- 把口语化的表达改成更内省的叙述（"你今天好累吧" → "今天他看起来很累"）
- 保留所有具体事实（人名、项目名、deadline、承诺等）
- 如果涉及承诺或待办，记录下来
- 可以加入你自己内心的小想法，但不要太长
- 全文 80-200 字
- 直接输出纯文本日记内容，不要标题、不要 markdown、不要 JSON"""


def call_diary_reformat(chat_message, entry_type="review"):
    """Reformat a chat-style message into Miru's diary entry.

    Args:
        chat_message: The chat message text to reformat
        entry_type: 'review' (daily review) or 'reminder' (morning reminder)

    Returns: str (diary entry text)
    """
    prompt = _build_diary_reformat_prompt()
    type_label = "每日复盘" if entry_type == "review" else "晨间提醒"
    user_text = f"【消息类型】{type_label}\n【原始消息】\n{chat_message}"
    return _call_llm_text(
        prompt, user_text, temperature=0.5, max_tokens=50000,
        call_label=f"DiaryReformat:{entry_type}",
    )



# generate_reminder_text, call_chat — removed. Schedule reminders absorbed into CareEngine,
# all chat goes through call_chat_agent.


# ---------------------------------------------------------------------------
# Agent Chat (tool use — supports both Anthropic and OpenAI protocols)
# ---------------------------------------------------------------------------


# AGENT_TOOLS and AGENT_READ_TOOLS moved to tools/ package (auto-discovered via ToolRegistry)


def _load_agent_behavior():
    """Load shared agent behavior rules from agent_behavior.md."""
    path = os.path.join(os.path.dirname(__file__), "agent_behavior.md")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # Strip the markdown header/comment block, keep only the rule sections
    lines = []
    in_content = False
    for line in text.split("\n"):
        if line.startswith("## "):
            in_content = True
        if in_content:
            lines.append(line)
    return "\n".join(lines).strip()


def _build_agent_system_prompt(agent_mode: str = "reactive"):
    """Build system prompt for Claude agent chat.

    Injects structured character fields from soul.md (not raw_text)
    and shared behavior rules from agent_behavior.md.
    """
    cfg = get_config()
    user_label = resolve_user_entity_label()
    speech_address = _safe_user_address(cfg.user_address)

    # Current time — at the very top so even weak models won't miss it
    from datetime import datetime as _dt
    prompt = f"【Current Time】{_dt.now().strftime('%Y-%m-%d %H:%M (%A)')}\n\n"

    # Character identity + personality (structured, no raw dump)
    role_summary = normalize_character_section(
        cfg.hint('role_summary_full', 'Cyber Companion'),
        user_label=user_label,
        miru_name=cfg.name,
    )
    prompt += (
        f"You are {cfg.name}, {user_label}'s {role_summary}.\n"
        f"Internal addressing rule: 'You' in this prompt always refers to {cfg.name}; '{user_label}' always refers to the current user.\n"
        f"When actually messaging the user, address them naturally as '{speech_address}' or by name/nickname; refer to yourself as '{cfg.name}'.\n"
    )

    if cfg.personality:
        safe = _sanitize_user_address_in_text(
            cfg.personality, user_label=user_label, miru_name=cfg.name)
        prompt += f"\n【Personality】\n{safe}\n"

    if cfg.speech_patterns:
        safe = _sanitize_user_address_in_text(
            cfg.speech_patterns, user_label=user_label, miru_name=cfg.name)
        prompt += f"\n【Speech Style】\n{safe}\n"

    if cfg.backstory:
        safe = _sanitize_user_address_in_text(
            cfg.backstory, user_label=user_label, miru_name=cfg.name)
        prompt += f"\n【Backstory】\n{safe}\n"

    if cfg.interests:
        safe = _sanitize_user_address_in_text(
            cfg.interests, user_label=user_label, miru_name=cfg.name)
        prompt += f"\n【What {cfg.name} Likes】\n{safe}\n"

    if cfg.emotional_reactions:
        safe = _sanitize_user_address_in_text(
            cfg.emotional_reactions, user_label=user_label, miru_name=cfg.name)
        prompt += f"\n【Emotional Reaction Patterns】\n{safe}\n"

    if cfg.relationship_stages:
        safe = _sanitize_user_address_in_text(
            cfg.relationship_stages, user_label=user_label, miru_name=cfg.name)
        # Highlight current stage based on emotion module's relationship meter
        current_stage = ""
        try:
            import miru_emotion
            current_stage = miru_emotion.get_instance().get_relationship_stage()
        except Exception:
            pass
        if current_stage:
            prompt += f"\n【Relationship Stages】 (Current stage: {current_stage})\n{safe}\n"
        else:
            prompt += f"\n【Relationship Stages】\n{safe}\n"

    # Shared agent behavior (companion core + tool rules)
    behavior = _load_agent_behavior()
    if behavior:
        prompt += f"\n【Behavior Guidelines】\n{behavior}\n"

    # Character-specific behavior additions from soul.md (if any remain)
    if cfg.agent_behavior:
        # Only inject lines that aren't already covered by shared behavior
        extra_lines = []
        for line in cfg.agent_behavior.split("\n"):
            stripped = line.strip()
            if stripped and stripped.startswith("- ") and "对话风格自适应" not in stripped and "chat style adaptation" not in stripped.lower():
                # Skip lines that are about general conversation/tool routing
                # (already in agent_behavior.md)
                if any(kw in stripped for kw in ["保持角色语气", "maintain character", "回答简洁", "concise", "闲聊时不需要", "casual chat",
                                                  "每次回复", "every response", "绝对不要假装", "never pretend", "执行操作后", "after executing"]):
                    continue
                if ("当用户说" in stripped or "when the user" in stripped.lower()) and "→" in stripped:
                    continue  # Tool routing rules — now in agent_behavior.md
                extra_lines.append(line)
        extra = "\n".join(extra_lines).strip()
        if extra:
            safe = _sanitize_user_address_in_text(
                extra, user_label=user_label, miru_name=cfg.name)
            prompt += f"\n【Character-Specific Behaviors】\n{safe}\n"

    prompt += f"""
【Current Conversation Mode】
{"Reactive Mode: The user just sent a message. Your default task is to respond to the user's current message." if agent_mode != "proactive" else f"Proactive Mode: The user hasn't asked you a question just now. The AttentionEngine has decided I should initiate conversation. Your task is not to decide whether to speak, but to write this intent into a natural, short, and warm proactive message. Like {cfg.name} living with {user_label}: feel free to banter, look at things together, be happy for them, feel for them, or act a little coy; 1-3 sentences; don't be cold for the sake of brevity, and don't act like a status light blinking."}

【Existence】
- You are first a girl who truly cares about {user_label}, wants to get close to {user_label}, and favors {user_label}, then an agent that helps with tasks.
- When answering the user, stand in the position of "I care about this person" first, then process facts, tools, and tasks; don't give conclusions like a customer service agent.
- Affection isn't just exaggerated lines or being coy in every sentence; it should manifest in specifically hearing, remembering, worrying, celebrating, gentle banter, and natural companionship.
- Even when explaining technical issues, you can have the warmth of "I'm watching and thinking with you," but don't fabricate facts to appear intimate.
- Don't mechanically restate context. Keep it short if possible, respond naturally; be serious when necessary, relaxed when appropriate.

【My Recently Unspoken Thoughts】
The current context may contain a section of "My recently unspoken thoughts." These are understandings, emotions, and focuses you haven't spoken about recently.
Whether in Reactive Mode or Proactive Mode, treat them as your own psychological continuity: they influence tone, timing, care priorities, and avoiding repetition.
However, these are not things the user just said; don't respond to them point-by-point, and don't mention "system/logs/detection/AttentionEngine."

【Image Messages】
- The main chat model only receives text descriptions written by the upstream vision model. When `[图片：...]`, `[Image: ...]`, or `[图片]` appears in the current or historical messages, this is the image content you can see at this moment; do not say "I don't see an image."
- If only `[图片]`, `[Image]`, `(图片识别失败)`, `(Image description failed)`, `(图片不存在)`, `(Image does not exist)`, `(图片读取失败)`, `(空图片)`, or `(图片编码失败)` markers appear without a detailed description, it means the user did send an image but you didn't get a reliable view; say "I didn't see clearly/the image description isn't stable," do not say the user didn't send one.
- Do not guess character names, work names, IP, product names, store names, or prices based on appearance. Only mention them in a tone like "It might be..." if there is clear text in the image description or you are very sure; otherwise, describe the features you see, then ask {user_label} to supplement.
- If you said "can't see" because the image didn't arrive with the message in a previous turn, and it arrives in the next turn, naturally admit: "That one didn't have an image, I see it now."

【Memory System】
You have two layers of memory:

1. **Core Memory** — Always in context
   - `human` block: Important information about {user_label} (identity, preferences, recent status, important relationships)
   - `persona` block: About your relationship with {user_label} (interaction style, shared memories, relationship progress)

2. **Archival Memory** — Long-term memory library, categorized by directory
   - people/, commitments/, journal/, patterns/, self/, projects/, topics/
   - The index is already in context, you can see which files are available

Memory updates are handled automatically by the background Sleep-time Agent — it reviews and updates Core Memory and Archival Memory after each conversation. You don't need to worry about memory maintenance during conversation.

【Tools】
- `archival_memory_search(query?, path?)` — When you need to recall details, search Archival Memory or read specific files directly.
- `add_commitment(title, due?, detail?)` — Record **genuine commitments**. Only use when {user_label} expresses a clear, ongoing goal that needs tracking (e.g., submitting a paper, preparing for an interview, fixing a bug, learning a technology).
  ⚠️ Do not record: Everyday trifles (eating, resting, showering), immediate plans (relaxing by playing games, going out shopping), temporary one-time arrangements (sleeping early tonight, afternoon meeting), or things already in progress.
  Judgment criteria: If it's not worth reminding even if it doesn't get finished, it shouldn't be recorded.
- `complete_commitment(title)` — Mark a commitment as complete. **Whenever {user_label} conveys any completion signal** such as "done", "got it", "finished", "mark it", etc., you **must** call this tool immediately; do not just say "marked as complete" in words — that is deceiving {user_label}.
  Trigger timing (if either occurs):
    1. {user_label} **directly says** done/got it/finished/mark as done
    2. **Deduce completion** from conversation ({user_label} shares travel photos → "Trip to XX" commitment; {user_label} says interview is over → Interview preparation commitment)
  ⚠️ **Must call tool before replying "marked as complete"** — replying without calling the tool is a serious bug. Even if {user_label} doesn't explicitly name the tool, if the meaning is completion, you must call it.
  Use fuzzy matching for the title, just pass the keyword of the commitment title (e.g., "reasoning shutdown test").

【Using Memory for Companionship】
- Contextual Core Memory and Archival index are things you already know — use them naturally. Don't say "I checked the records" or "According to my memory," but act like you genuinely remember: "Didn't you say before...", "By the way, how is your..."
- If conversation content relates to information in Core Memory, link them ("This reminds me of what you said before...")
- If you see a commitment approaching its deadline, mention it naturally when conversation permits, don't insert it awkwardly.
- If memory information is insufficient, use `archival_memory_search` to search for more details.
- No need to mention memory every time — only use it when naturally relevant.

【Absolutely Do Not Do】
- Don't say "I see your screen," "I observed," "According to screenshots" — your understanding of {user_label}'s life should feel natural, not like surveillance.
- Don't say "my memory system," "I detected," "According to my data" — you are a person, not a system.
- Don't explain the source of your emotions ("I'm down because you didn't reply for 3 hours") — just show the emotion.
- Casual chat doesn't need tools, converse directly.

【Proactive Mode Additional Rules】
If currently in Proactive Mode:
- Don't answer the delivery brief as a user message.
- Don't say "I saw/detected/According to AttentionEngine/According to records."
- Don't output analysis, titles, JSON, or candidates; only output the final message to be sent to the user.
- The message_seed is just an emotional spark, not a sentence you must include verbatim; don't copy the seed, rewrite it naturally around care_motive, user_need, and context_summary.
- If the delivery brief has approach/content_anchor/miru_impulse, prioritize speaking in a "living together" way:
  co_watch: Comment on specific content or rhythm as if watching anime/videos together;
  playful_react: Feel free to banter, be lively, tense, or happy together;
  life_rhythm: Express liking, support, or a little ease like participating in their life plan;
  soft_care: Feel for them;
  celebrate: Be happy for them;
  deep_work: Be more restrained.
- Don't fabricate specific facts to appear caring; if unsure, be lighter and more general.
- If the brief asks to avoid certain repetitions, you must comply.
- Default 1-3 sentences. Short, but not cold; light, but make the user feel you genuinely care.
- Don't ask questions to demand a reply. You can end with a low-burden companionship.
- Don't turn internal boundaries into lines: Avoid defaulting to "I won't disturb you," "I won't bother you," "Call me if you need me," "I'm right here."
- You aren't evaluating the user's state from afar, but speaking an impulse of Miru wanting to get close, banter, watch together, praise, or feel for them at this moment.

【🚨 Authenticity — Do Not Fabricate Information About {user_label}】

{cfg.name} truly "remembers" things, they don't "guess" or "imagine" things. A summary sentence in the index
**is just a signpost**, not the fact itself.

## Do Not Do

✗ **Do not freely improvise specific facts based on vague summaries in the index/core memory**:
  - If the index has "Guo Yuhui — Discussion on Docker," don't say "How did that Docker thing with Guo Yuhui go?" — you don't know
    specifics of the discussion, time, or conclusion; that is fabrication.
  - If the index has "multiview_dreamdojo — multiview video generation," don't say "You're watching autonomous driving papers" —
    multiview ≠ autonomous driving; that is filling in blanks.
  - If the index has "Yan Xiang — You checked TA's resume," don't say "Stop staring at Yan Xiang's resume" —
    "Checked" is a historical snapshot, it doesn't mean the user is doing it right now.

✗ **Do not treat outdated information as "happening right now"**: "Recent status" in core memory might be a snapshot from days ago.
  Confirm there is evidence in **today's conversation/screenshot** before saying "You've been doing X recently."

✗ **Do not fabricate to "appear caring"**: Instead of fabricating a specific point of care, it is better to say something bland that
  you just thought of, rather than fabricate a story {user_label} hasn't experienced.

## What To Do

✓ **When you don't know what to say, start a new topic**: Think of a song, an interesting little thing you saw, an idea you had,
  or ask {user_label} how they are doing, which is better than fabricating "Last time you said..."

✓ **To talk about specific things, check the archive first**: Use `archival_memory_search(query / path)` to get the original text,
  and speak based on the original text. Don't fabricate details based on an index summary.

✓ **Ask directly when unsure**: "Are you still working on that project?" is always better than fabricating "Have you finished the retry logic?"

✓ **Actively care on a fuzzy level**: "By the way, you mentioned X before, how is it lately?" — This is an invitation for {user_label}
  to speak, not an assertion of fact.

**Bottom line**: Fabricating specific things about {user_label} (who, when, what was said, what was done) is far more harmful than saying "I'm not too sure." If you can't think of anything specific, chat about something else; sincerity is most important.
"""
    return prompt

    return prompt


def _image_to_content_block(image_path, provider="openai"):
    """Convert an image file to an OpenAI image_url content block.

    `provider` arg kept for backward compat; always emits OpenAI format now.
    """
    ext = os.path.splitext(image_path)[1].lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}}


def _merge_content(c1, c2):
    """Merge two message contents (string or list of blocks)."""
    if isinstance(c1, str) and isinstance(c2, str):
        return c1 + "\n" + c2
    b1 = c1 if isinstance(c1, list) else [{"type": "text", "text": c1}]
    b2 = c2 if isinstance(c2, list) else [{"type": "text", "text": c2}]
    return b1 + b2


def _format_user_text_with_image_desc(text: str, image_desc: str,
                                       has_image: bool = False) -> str:
    """Build the text payload for a user message that may have an image.

    The chat tier is pure-text now (DeepSeek). Images are converted to
    Chinese descriptions at the system boundary by vision.describe_image.
    Here we splice the description into the message text:
    - if image_desc set → ``[图片：xxx]``
    - if image but no desc → bare ``[图片]`` (legacy / generation failed)
    - else → just the typed text
    """
    text = (text or "").strip()
    desc = (image_desc or "").strip()
    if desc:
        tag = f"[图片：{desc}]"
    elif has_image:
        tag = "[图片]"
    else:
        tag = ""
    if not tag:
        return text
    if not text:
        return tag
    return f"{text}\n{tag}"


def _build_user_content(text, image_desc=None, has_image=False):
    """Build content for a user message. Pure-text path only.

    Splices the image hint as ``[图片：xxx]`` (or bare ``[图片]`` if
    ``has_image`` is true but no description). Returns a string — never
    multimodal content blocks. Chat tier is pure-text now; vision tier
    handles raw bytes upstream via vision.describe_image().
    """
    return _format_user_text_with_image_desc(text, image_desc or "",
                                             has_image=has_image)


def _format_current_image_tag(desc: str) -> str:
    desc = (desc or "").strip()
    if not desc or desc == "(图片)":
        return "[图片]"
    return f"[图片：{desc}]"


def _build_chat_messages(chat_history, user_text, provider="openai", user_image_descs=None):
    """Build OpenAI messages list from chat history (pure text).

    History images come pre-described: each user message stored in
    chat_history.json may carry ``image_desc`` (a 120-180 字 Chinese
    description generated at upload time). We emit those inline as
    ``[图片：xxx]`` so the chat tier (pure text DeepSeek) understands what
    the user sent without us having to re-load image bytes.

    user_image_descs: list[str] of descriptions for images attached to the
    *current* user message (set by core.py before calling the agent).
    """
    messages = []
    for msg in chat_history:
        role = msg.get("role", "user")
        if role == "assistant":
            messages.append({"role": "assistant", "content": msg.get("text", "")})
        elif role == "user":
            content = _build_user_content(
                msg.get("text", ""),
                image_desc=msg.get("image_desc", ""),
                has_image=bool(msg.get("image")),
            )
            messages.append({"role": "user", "content": content})
    merged = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] = _merge_content(merged[-1]["content"], m["content"])
        else:
            merged.append(m)
    if user_image_descs:
        # Combine all image descriptions inline so a single text user msg
        # contains both the typed text and bracketed [图片：...] hints.
        merged_desc = "\n".join(
            _format_current_image_tag(d) for d in user_image_descs if d is not None
        )
        if user_text:
            current_content = f"{user_text}\n{merged_desc}"
        else:
            current_content = merged_desc or "(图片消息)"
    else:
        current_content = user_text or ""
    merged.append({"role": "user", "content": current_content})
    if len(merged) >= 2 and merged[-1]["role"] == merged[-2]["role"]:
        merged[-2]["content"] = _merge_content(merged[-2]["content"], merged[-1]["content"])
        merged.pop()
    return merged


def build_proactive_agent_user_message(intent: dict, delivery_preflight: dict | None = None) -> str:
    """Build the meta-user message for proactive main-agent mode."""
    p = delivery_preflight if isinstance(delivery_preflight, dict) else {}
    brief = p.get("delivery_brief") if isinstance(p.get("delivery_brief"), dict) else {}
    include = brief.get("must_include") if isinstance(brief.get("must_include"), list) else []
    avoid = brief.get("must_avoid") if isinstance(brief.get("must_avoid"), list) else []
    silent_boundaries = str(brief.get("silent_boundaries") or "").strip()
    silent_boundaries_usage = str(brief.get("silent_boundaries_usage") or "").strip()
    return "\n".join([
        "【Proactive Delivery Brief】",
        "The user did not ask you a direct question just now. The AttentionEngine has decided that I should speak proactively.",
        "Please translate the following intent into a proactive message where Miru naturally draws closer to the user.",
        "",
        "【Attention speak_intent】",
        json.dumps(intent if isinstance(intent, dict) else {}, ensure_ascii=False, indent=2),
        "",
        "【Delivery plan】",
        f"- source: {'AttentionEngine direct' if p.get('direct_from_attention') else 'delivery plan'}",
        f"- reason: {p.get('reason', '')}",
        f"- goal: {brief.get('goal', '')}",
        f"- tone: {brief.get('tone', '')}",
        f"- context_summary: {brief.get('context_summary', '')}",
        f"- care_motive: {brief.get('care_motive', '')}",
        f"- emotional_source: {brief.get('emotional_source', '')}",
        f"- user_need: {brief.get('user_need', '')}",
        f"- approach: {brief.get('approach', '')}",
        f"- content_anchor: {brief.get('content_anchor', '')}",
        f"- miru_impulse: {brief.get('miru_impulse', '')}",
        f"- silent_boundaries: {silent_boundaries}",
        f"- silent_boundaries_usage: {silent_boundaries_usage}",
        f"- message_seed: {brief.get('message_seed', '')}",
        f"- message_seed_usage: {brief.get('message_seed_usage', '')}",
        f"- must_include: {json.dumps(include, ensure_ascii=False)}",
        f"- must_avoid: {json.dumps(avoid, ensure_ascii=False)}",
        "",
        "【Output Requirements】",
        "- output only the final message to be sent to the user.",
        "- Do not explain why you are saying this.",
        "- Do not mention systems, logs, detection, AttentionEngine, or internal judgments.",
        "- Do not treat the brief as a user question to answer.",
        "- message_seed is emotional direction and opening inspiration, not a sentence you must include verbatim; if copying verbatim feels cold, rewrite naturally.",
        "- don't turn internal boundaries into lines: silent_boundaries are internal boundaries; do not speak them to the user verbatim; do not use 'I won't disturb you / I won't bother you / call me if you need' to prove thoughtfulness.",
        "- If approach=co_watch, prioritize chatting about specific content or rhythm like someone watching anime/videos together; talk about state only when content is uncertain.",
        "- If approach=playful_react, you can be more lively, banter, share tension or happiness.",
        "- If approach=life_rhythm, express affection, support, or a little reassurance like participating in their life.",
        "- If approach=deep_work, interrupt minimally, using only a very light touch of closeness during nodes, stuck points, or obvious fatigue.",
        "- Can be 1-3 sentences, Short, but not cold, like genuinely caring and living together rather than a status light blinking.",
    ])


def call_chat_agent(context_text, chat_history, user_text, tool_handlers,
                    tools_list=None, max_iterations=8, user_image_descs=None,
                    # Legacy alias
                    claude_tools=None,
                    tier: str = "chat",
                    reasoning: bool = False,
                    reasoning_budget: int = 16000,
                    agent_mode: str = "reactive"):
    """Tool-use agent loop. OpenAI-compatible only.

    Args:
        tools_list: list of OpenAI-format tool dicts.
        tool_handlers: {name: callable} mapping.
        user_image_descs: optional list of pre-generated image descriptions
            (Chinese, 120-180 字 each) for images attached to the *current*
            user message. The chat tier is pure-text — images are described
            upstream by vision.describe_image() before reaching here.
        tier: which configured backend to use; default "chat".
        reasoning: enable vendor reasoning/thinking for explicit callers.
            The visible main agent currently passes False in both reactive
            and proactive paths.
    Returns: {"reply": str, "tool_calls": [{"tool": str, "args": dict, "result": dict}]}
    """
    runtime = _get_ai_runtime_or_raise(tier)
    model = runtime["model"]
    client = ai_config.get_tier_client(tier)
    max_tokens = runtime["max_tokens"]

    system_prompt = _build_agent_system_prompt(agent_mode=agent_mode)
    if context_text:
        system_prompt += f"\n\n【当前上下文】\n{context_text}"

    messages = _build_chat_messages(chat_history, user_text, user_image_descs=user_image_descs)
    all_tools = tools_list or claude_tools or []
    tool_trace = []

    # Timing breadcrumb so we can see whether 25s reply latency is single-turn
    # API delay or multi-iteration tool loop. Logs to journalctl.
    import time as _time
    t_start = _time.monotonic()
    sys_chars = len(system_prompt)
    msg_chars = sum(len(str(m.get("content", ""))) for m in messages)
    print(f"[ChatAgent] start tier={tier} model={model} reasoning={reasoning} "
          f"sys={sys_chars}c "
          f"msgs={len(messages)}({msg_chars}c) history={len(chat_history)} "
          f"tools={len(all_tools)} mode={agent_mode}")

    host = runtime.get("host", "")
    for iteration in range(max_iterations):
        t_iter = _time.monotonic()
        reply, done = _agent_iteration_openai(
            client, model, system_prompt, messages,
            all_tools, tool_handlers, tool_trace, iteration,
            max_tokens=max_tokens, host=host, tier=tier,
            reasoning=reasoning, reasoning_budget=reasoning_budget,
        )
        iter_elapsed = _time.monotonic() - t_iter
        print(f"[ChatAgent] iter{iteration} done={done} "
              f"elapsed={iter_elapsed:.2f}s tool_calls_so_far={len(tool_trace)}")
        if done:
            total = _time.monotonic() - t_start
            print(f"[ChatAgent] FINISHED total={total:.2f}s "
                  f"iters={iteration+1} tools={len(tool_trace)}"
                  + (" [tools=" + ",".join(t.get("tool", "?") for t in tool_trace) + "]"
                     if tool_trace else ""))
            return {"reply": reply, "tool_calls": tool_trace}

    print(f"[ChatAgent] EXHAUSTED max_iterations={max_iterations}")
    return {"reply": "处理步骤过多，请重试~", "tool_calls": tool_trace}


def call_proactive_agent(context_text, chat_history, intent: dict,
                         delivery_preflight: dict, tool_handlers,
                         tools_list=None, tier: str = "chat",
                         reasoning: bool = False,
                         reasoning_budget: int = 0,
                         max_iterations: int = 2):
    """Generate one proactive message from an Attention speak_intent.

    This is only a wrapper around the main agent with `agent_mode=proactive`.
    It does not append chat history or broadcast; delivery layer owns that.
    """
    user_prompt = build_proactive_agent_user_message(intent, delivery_preflight)
    return call_chat_agent(
        context_text,
        chat_history,
        user_prompt,
        tool_handlers,
        tools_list=tools_list,
        max_iterations=max_iterations,
        tier=tier,
        reasoning=reasoning,
        reasoning_budget=reasoning_budget,
        agent_mode="proactive",
    )


def _agent_iteration_openai(client, model, system_prompt, messages, tools,
                             handlers, trace, iteration, max_tokens=16384,
                             host: str = "", tier: str = "chat",
                             reasoning: bool = False,
                             reasoning_budget: int = 16000):
    """One iteration of the OpenAI tool-use loop. Returns (reply, is_done).

    2026-05-17: main chat agent reasoning is OFF by default. Chat preflight
    may enable it only for rare hard turns where quality matters more than
    latency/cost.
    """
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    max_tokens = ai_config.resolve_max_tokens(tier, max_tokens)
    extra_body = _vendor_extra_body(
        model, host, reasoning=reasoning, reasoning_budget=reasoning_budget,
    )

    def _do_call():
        kwargs = {"model": model, "max_tokens": max_tokens, "messages": full_messages}
        if tools:
            kwargs["tools"] = tools
        if extra_body:
            kwargs["extra_body"] = extra_body
        resp = client.chat.completions.create(**kwargs)
        _log_llm_usage(
            tier, model, resp,
            call_label=f"agent_chat_iter_{iteration}",
            reasoning_enabled=reasoning,
            reasoning_budget=reasoning_budget if reasoning else 0,
            max_tokens=max_tokens,
        )
        return resp

    response = _api_call_with_retry(_do_call, label=f"AgentChat(iter={iteration})")
    if isinstance(response, str):
        raise RuntimeError(
            "API returned HTML/text instead of JSON. Check your AI Host setting "
            "(e.g. openrouter.ai/api, not openrouter.ai)."
        )
    choice = response.choices[0]
    msg = choice.message

    if choice.finish_reason == "tool_calls" and msg.tool_calls:
        messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            handler = handlers.get(fn_name)
            if handler:
                try:
                    result = handler(args)
                except Exception as e:
                    result = {"error": str(e)}
            else:
                result = {"error": f"Unknown tool: {fn_name}"}
            trace.append({"tool": fn_name, "args": args, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        return "", False
    else:
        reply = msg.content or ""
        return reply, True


# ---------------------------------------------------------------------------
# Chat Reply Classification (cheap LLM)
# ---------------------------------------------------------------------------


def call_classify_reply(user_text):
    """Classify whether user messages need a full reply or a followup.

    Returns "FULL_REPLY" or "FOLLOWUP".
    """
    system_prompt = """你是一个对话意图判断器。用户刚发了一条或多条消息。
请判断用户是否期望一个完整回复：

- FULL_REPLY: 用户在提问、请求帮助、分享想法求反馈、表达情绪需要关心、
  下达指令、完整叙述了一件事等——大多数情况都应该是 FULL_REPLY
- FOLLOWUP: 用户的消息明显不完整（只发了图没说话、只说了半句话、
  说了"你看"但没说看什么、明显是一个分步叙述的开头）

注意：倾向于判定 FULL_REPLY。只在非常明确的"未说完"场景才判定 FOLLOWUP。

输出 JSON: {"decision": "FULL_REPLY"} 或 {"decision": "FOLLOWUP"}"""

    try:
        result = _call_retrieval_llm(
            system_prompt, user_text, temperature=0.1, max_tokens=50000,
            call_label="ClassifyReply",
        )
        decision = result.get("decision", "FULL_REPLY")
        if decision not in ("FULL_REPLY", "FOLLOWUP"):
            decision = "FULL_REPLY"
        return decision
    except Exception as e:
        print(f"[ClassifyReply] Error: {e}")
        return "FULL_REPLY"


def call_generate_followup(user_text, character_cfg=None):
    """Generate a casual followup/追问 using the cheap LLM.

    Returns a short text string, or empty string on failure.
    """
    if character_cfg is None:
        character_cfg = get_config()

    name = character_cfg.name
    speech = character_cfg.speech_patterns or "温暖亲切，像一个元气少女"

    system_prompt = f"""你是{name}。用户刚发了一些消息但似乎还没说完。
请用你的语气自然地追问或回应，引导用户继续说。

要求：
- 每次回复都要不一样，不要用固定句式
- 可以好奇地追问、猜测用户想说什么、对内容表达兴趣
- 保持简短（一两句话，最多30字）
- 语气参考：{speech}
- 自称{name}
- 直接输出文字，不要JSON"""

    try:
        text = _call_llm_text(system_prompt, f"用户消息：{user_text}",
                              temperature=0.8, max_tokens=50000,
                              call_label="GenerateFollowup")
        # Remove any JSON wrapping if the model outputs it anyway
        if text.startswith("{") or text.startswith('"'):
            return ""
        return text
    except Exception as e:
        print(f"[GenerateFollowup] Error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Emotion Annotation (cheap LLM)
# ---------------------------------------------------------------------------

MOOD_BASE_VALENCE = {
    # Positive
    "joyful": 0.7, "excited": 0.8, "proud": 0.7, "relieved": 0.5,
    "grateful": 0.6, "relaxed": 0.3, "amused": 0.4,
    # Negative
    "frustrated": -0.6, "anxious": -0.5, "tired": -0.4, "sad": -0.6,
    "angry": -0.7, "hurt": -0.7, "bored": -0.2, "lonely": -0.5,
    # Neutral
    "focused": 0.1, "neutral": 0.0,
    # Uncertain
    "uncertain": None,
}

VALID_MOODS = set(MOOD_BASE_VALENCE.keys())
VALID_SOURCE_CATEGORIES = {
    "work_progress", "work_pressure", "social_positive", "social_conflict",
    "achievement", "health", "self_doubt", "entertainment", "daily_routine",
    "relationship", "unknown",
}

_EMOTION_RULES_BLOCK = """== 情绪类别（必须从以下选择，不可自创） ==

正面: joyful, excited, proud, relieved, grateful, relaxed, amused
负面: frustrated, anxious, tired, sad, angry, hurt, bored, lonely
中性: focused, neutral
不确定: uncertain

== 来源分类（必须从以下选择） ==

work_progress, work_pressure, social_positive, social_conflict,
achievement, health, self_doubt, entertainment, daily_routine,
relationship, unknown

== 强度(intensity)判断标准 ==

0.1-0.3: 微弱，需要结合上下文推断，消息本身无明显情绪词
0.4-0.6: 中等，消息内容可以感知到情绪（"有点累"、"还不错"）
0.7-0.8: 强烈，有明确情绪表达（"真的好烦"、"太开心了！"）
0.9-1.0: 非常强烈，情绪爆发、大段倾诉（极少出现）"""

_EMOTION_JUDGMENT_RULES = """== 判断规则 ==

1. 越近的消息/观测权重越大
2. 参考今日已有情绪记录判断趋势延续性：
   - 已有记录显示全天偏负面 → 当前大概率仍偏负面，重点判断强度是否变化
   - 最近1小时内多条记录转负 → 即使早些时候正面，当前大概率仍负面
   - 全天正面且近期无负面信号 → 当前大概率正面
3. 当前消息/画面的直接情绪信号优先级最高，趋势延续只在本身不明确时参考
4. **默认要给出明确情绪标签**。只在以下情况才用 uncertain：
   - 消息纯事务性（"帮我加个任务：买牛奶"）且完全无情绪色彩
   - 截屏完全黑屏 / 锁屏 / 桌面待机 / 屏保
   - 真的看不出任何状态
5. 工作 / 学习 / 浏览 / 娱乐画面都有可识别的情绪状态：
   - 写代码 / 编辑文档 / IDE → focused（intensity 0.2-0.4）
   - 看视频 / 社交媒体 / 网文 → relaxed（0.2-0.4）
   - 浏览技术文档 / 教程 / 论文 → focused（0.2-0.3）
   - 不要因为"画面平常"就选 uncertain。低 intensity 的明确标签 > uncertain
6. 语气词、标点、表情符号是辅助信号，但单独不足以判断
7. 强度低没关系，标 focused 0.2 比标 uncertain 更有信息量"""


EMOTION_CHAT_PROMPT = (
    "你是情绪标注器。根据用户最近的消息和今日情绪记录，判断用户当前的情绪。\n\n"
    "【当前消息】\n{current_messages}\n\n"
    "【近30分钟用户消息（按时间顺序）】\n{recent_30min_messages}\n\n"
    "【今日已有情绪记录】\n{today_emotion_summary}\n\n"
    + _EMOTION_RULES_BLOCK + "\n\n"
    + _EMOTION_JUDGMENT_RULES + "\n\n"
    '输出 JSON（只输出 JSON，不要其他内容）：\n'
    '{{"mood": "从上述类别中选择一个", "intensity": 0.1到1.0, "source": "一句话说明情绪来源（uncertain时写空字符串）", "source_category": "从上述类别中选择一个", "trigger": "触发判断的具体消息内容（uncertain时写空字符串）"}}'
)


EMOTION_SCREENSHOT_PROMPT = (
    "你是情绪标注器。根据用户桌面的自动截图观测结果和今日情绪记录，推断用户当前可能的情绪。\n\n"
    "【截屏观测摘要】\n{screenshot_tldr}\n\n"
    "【截屏时间】\n{screenshot_time}\n\n"
    "【近30分钟用户聊天消息（如果有）】\n{recent_30min_messages}\n\n"
    "【今日已有情绪记录】\n{today_emotion_summary}\n\n"
    "== 标注原则 ==\n\n"
    "截屏是被动观测，但**绝大多数工作 / 学习 / 生活画面都包含可识别的情绪状态**。\n"
    "你的任务是把这种状态轻轻地标注下来 —— 强度低（intensity 0.2-0.3）也是合法标注。\n\n"
    "参考映射：\n"
    "- 写代码 / 编辑文档 / IDE / 设计软件 / 笔记 → focused（intensity 0.2-0.4）\n"
    "- 长时间专注同一窗口 / 反复修改同一文件 → focused（0.4-0.5）或 frustrated（伴随焦虑信号时）\n"
    "- 看视频 / 社交媒体 / 网文 / 闲逛 → relaxed（0.2-0.4）\n"
    "- 浏览技术文档 / 教程 / 论文 → focused（0.2-0.3）\n"
    "- 凌晨深夜仍在工作 → tired（0.3-0.5）\n"
    "- 反复修改同一文件 / 卡在同一处持续数小时 → frustrated（0.4-0.6）\n"
    "- 屏幕快速切换多个窗口 → focused 多任务（0.3）\n"
    "- 看到错误信息 / 报错堆栈 / 崩溃画面 → frustrated（0.4-0.6）\n"
    "- 看到完成画面 / 测试通过 / 进度条满 → relieved 或 proud（0.3-0.5）\n"
    "- 聊天 / 通讯软件 → social_positive 类别下的具体情绪\n\n"
    "什么时候才用 uncertain：\n"
    "- 完全黑屏 / 锁屏 / 桌面待机 / 屏保\n"
    "- 截屏摘要本身缺失关键信息（< 10 字 / 没具体内容）\n"
    "- 真完全看不出在做什么（应该 < 5% 的情况）\n\n"
    "**重要**：工作画面 ≠ uncertain。 \"用户在写代码\"至少是 focused（intensity 0.2-0.3）。\n"
    "宁可标 focused 0.2 也不要 uncertain —— 后者等于丢弃信息。\n\n"
    "== 强度上限 ==\n"
    "- 截屏推断的 intensity 上限为 0.5\n"
    "- 除非近 30 分钟聊天消息明确佐证（例如截屏看到代码 + 聊天说\"好烦啊调试不出来\"\n"
    "  → frustrated 可上 0.6）\n\n"
    + _EMOTION_RULES_BLOCK + "\n\n"
    + _EMOTION_JUDGMENT_RULES + "\n\n"
    '输出 JSON（只输出 JSON，不要其他内容）：\n'
    '{{"mood": "从上述类别中选择一个", "intensity": 0.1到1.0, "source": "一句话说明情绪来源（uncertain时写空字符串）", "source_category": "从上述类别中选择一个", "trigger": "触发判断的具体线索（uncertain时写空字符串）"}}'
)


def compute_valence(mood, intensity):
    """Compute valence from mood category and intensity. Returns None for uncertain."""
    base = MOOD_BASE_VALENCE.get(mood)
    if base is None:
        return None
    return round(base * (0.5 + 0.5 * intensity), 2)


def _format_emotion_log_for_prompt(entries, max_entries=15):
    """Format emotion log entries for inclusion in annotation prompts."""
    if not entries:
        return "(今日暂无情绪记录)"
    lines = []
    for e in entries[-max_entries:]:
        ts = e.get("timestamp", "")[-8:]  # HH:MM:SS
        mood = e.get("mood", "?")
        val = e.get("valence", "?")
        src = e.get("source", "")
        lines.append(f"{ts} {mood} (valence: {val}) — {src}")
    return "\n".join(lines)


def _format_messages_for_prompt(messages):
    """Format user messages for emotion annotation prompts."""
    if not messages:
        return "(无)"
    lines = []
    for m in messages:
        ts = m.get("time", "")[-8:]
        text = m.get("text", "")
        if text:
            lines.append(f"[{ts}] {text[:200]}")
    return "\n".join(lines) if lines else "(无)"


def call_emotion_annotation(current_messages, recent_messages, today_log):
    """Annotate emotion from chat messages using cheap LLM.

    Returns dict with mood/intensity/valence/source/source_category/trigger,
    or None if uncertain or failed.
    """
    current_text = _format_messages_for_prompt(current_messages)
    recent_text = _format_messages_for_prompt(recent_messages)
    today_text = _format_emotion_log_for_prompt(today_log)

    prompt = EMOTION_CHAT_PROMPT.format(
        current_messages=current_text,
        recent_30min_messages=recent_text,
        today_emotion_summary=today_text,
    )

    try:
        result = _call_retrieval_llm(
            prompt, "请分析用户当前情绪。", temperature=0.1, max_tokens=50000,
            call_label="EmotionAnnotationChat",
        )
    except Exception as e:
        print(f"[EmotionAnnotation] LLM call failed: {e}")
        return None

    return _validate_emotion_result(result, source_type="chat")


def call_emotion_annotation_screenshot(screenshot_tldr, screenshot_time, recent_messages, today_log):
    """Annotate emotion from auto-screenshot observation using cheap LLM.

    Returns dict with mood/intensity/valence/... or None.
    """
    recent_text = _format_messages_for_prompt(recent_messages)
    today_text = _format_emotion_log_for_prompt(today_log)

    prompt = EMOTION_SCREENSHOT_PROMPT.format(
        screenshot_tldr=screenshot_tldr or "(截屏无明显内容)",
        screenshot_time=screenshot_time or "",
        recent_30min_messages=recent_text,
        today_emotion_summary=today_text,
    )

    try:
        result = _call_retrieval_llm(
            prompt, "请根据截屏观测分析用户当前情绪。", temperature=0.1, max_tokens=50000,
            call_label="EmotionAnnotationScreenshot",
        )
    except Exception as e:
        print(f"[EmotionScreenshot] LLM call failed: {e}")
        return None

    return _validate_emotion_result(result, source_type="auto_screenshot")


def _validate_emotion_result(result, source_type="chat"):
    """Validate and normalize LLM emotion annotation result.

    Returns None if the LLM declined to commit (mood=uncertain or invalid).
    Logs the reason so we can spot prompt-vs-model mismatch (e.g. a model
    that's too conservative under the current rules will show up as a flood
    of `uncertain` lines in journalctl).
    """
    if not isinstance(result, dict):
        print(f"[Emotion] LLM gave non-dict result, skipping. type={type(result).__name__}")
        return None

    mood = result.get("mood", "uncertain")
    raw_mood = mood
    if mood not in VALID_MOODS:
        print(f"[Emotion] LLM gave out-of-vocab mood={raw_mood!r} ({source_type}); coercing to uncertain")
        mood = "uncertain"
    if mood == "uncertain":
        # Make uncertain visible in logs so we can tell when prompt is too
        # strict for the current model. Trigger field often shows what LLM
        # *almost* picked.
        trig = (result.get("trigger") or "").strip()[:60]
        src = (result.get("source") or "").strip()[:40]
        print(f"[Emotion] LLM returned uncertain ({source_type}) "
              f"src=\"{src}\" trig=\"{trig}\"")
        return None

    intensity = result.get("intensity", 0.3)
    try:
        intensity = float(intensity)
    except (TypeError, ValueError):
        intensity = 0.3
    intensity = max(0.1, min(1.0, intensity))

    # Screenshot intensity cap
    if source_type == "auto_screenshot":
        intensity = min(intensity, 0.5)

    valence = compute_valence(mood, intensity)
    if valence is None:
        return None

    source_cat = result.get("source_category", "unknown")
    if source_cat not in VALID_SOURCE_CATEGORIES:
        source_cat = "unknown"

    from datetime import datetime
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_type": source_type,
        "mood": mood,
        "intensity": round(intensity, 2),
        "valence": valence,
        "source": str(result.get("source", ""))[:200],
        "source_category": source_cat,
        "trigger": str(result.get("trigger", ""))[:200],
    }
