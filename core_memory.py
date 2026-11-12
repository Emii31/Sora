"""Core Memory — always-in-context, agent-editable memory blocks.

Inspired by Letta/MemGPT's two-tier architecture:
- Core Memory: small, always injected into system prompt, agent can edit
- Archival Memory: large, searchable, agent can write + search

This module manages core memory blocks stored in data/core_memory.json.
"""

import json
import os
import threading
from typing import Optional

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
CORE_MEMORY_PATH = os.path.join(DATA_DIR, "core_memory.json")

_lock = threading.Lock()

# Block size limits.
# These blocks are injected into EVERY chat-agent prompt (see core.py
# _build_chat_context → format_for_context), so a large block bloats every
# turn's input tokens. We keep them small on purpose:
#   limit = 5000 chars  (~ 1500 Chinese chars, ~ 1.5K tokens)
# Soft trigger: when content exceeds SOFT_RATIO × limit we proactively
# consolidate the block down to TARGET_RATIO × limit. This keeps the
# block from creeping up to the hard limit and being a steady-state
# context bloat. consolidate uses a cheap LLM (memory tier).
DEFAULT_BLOCK_LIMIT = 5000
SOFT_RATIO = 0.80      # consolidate when >= 80% full
TARGET_RATIO = 0.60    # consolidate down to 60% full

DEFAULT_BLOCKS = {
    "human":   {"label": "human",   "value": "", "limit": DEFAULT_BLOCK_LIMIT},
    "persona": {"label": "persona", "value": "", "limit": DEFAULT_BLOCK_LIMIT},
}


def _core_memory_path() -> str:
    try:
        from flask import g
    except ImportError:
        return CORE_MEMORY_PATH
    try:
        data_dir = getattr(g, "user_data_dir", None)
    except RuntimeError:
        return CORE_MEMORY_PATH
    if data_dir:
        import storage
        return os.path.join(storage.get_data_dir(), "core_memory.json")
    return CORE_MEMORY_PATH


def _load() -> dict:
    p = _core_memory_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {k: dict(v) for k, v in DEFAULT_BLOCKS.items()}


def _save(data: dict):
    p = _core_memory_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_all_blocks() -> dict[str, str]:
    """Return {label: value} for all blocks. Used for context injection."""
    with _lock:
        data = _load()
        return {k: v.get("value", "") for k, v in data.items()}


def get_block(label: str) -> Optional[str]:
    """Read a single block's value."""
    with _lock:
        data = _load()
        block = data.get(label)
        if block is None:
            return None
        return block.get("value", "")


def replace(label: str, old_text: str, new_text: str) -> dict:
    """Precise find-and-replace in a core memory block (first occurrence).

    Returns {"ok": True, "new_len": int} on success.
    On failure (old_text not found), returns {"ok": False, "current_value": str}.
    """
    with _lock:
        data = _load()
        if label not in data:
            return {"ok": False, "error": f"Unknown block: {label}"}

        block = data[label]
        current = block.get("value", "")
        limit = block.get("limit", 100000)

        if old_text not in current:
            return {"ok": False, "error": "old_text not found in block", "current_value": current}

        new_value = current.replace(old_text, new_text, 1)
        if len(new_value) > limit:
            return {"ok": False, "error": f"Result exceeds {limit} char limit ({len(new_value)} chars)",
                    "current_value": current}

        block["value"] = new_value
        _save(data)
        return {"ok": True, "new_len": len(new_value)}


def append(label: str, content: str, auto_consolidate: bool = True) -> dict:
    """Append content to a core memory block.

    Two-stage growth control:
      1. Soft trigger (after a successful append): if the new size crosses
         SOFT_RATIO × limit, proactively consolidate down to TARGET_RATIO.
         This prevents the block from creeping up over time and bloating
         the chat-agent prompt every turn.
      2. Hard fallback: if the new content would overflow the limit
         outright, run consolidate first, then retry the append. Same
         behavior as before; just kept as a safety net.

    Returns {"ok": True, "new_len": int} on success.
    On failure: {"ok": False, "error": str, "current_value": str, "chars_remaining": int}
    """
    with _lock:
        data = _load()
        if label not in data:
            return {"ok": False, "error": f"Unknown block: {label}"}

        block = data[label]
        current = block.get("value", "")
        limit = block.get("limit", DEFAULT_BLOCK_LIMIT)
        new_value = current + content

        if len(new_value) <= limit:
            block["value"] = new_value
            _save(data)
            new_len = len(new_value)
            soft_threshold = int(limit * SOFT_RATIO)
            crossed_soft = new_len >= soft_threshold and len(current) < soft_threshold
        else:
            new_len = None
            crossed_soft = False

    # Successful append above — but if we just crossed the soft threshold,
    # fire a consolidation (single attempt, outside the lock since it's
    # a cheap LLM call). Failure is non-fatal — block stays at the new
    # size, next append will retry the threshold check.
    if new_len is not None:
        if auto_consolidate and crossed_soft:
            print(f"[CoreMemory] Block '{label}' crossed soft threshold "
                  f"({new_len}/{limit}), proactively consolidating...")
            try:
                consolidate(label)
            except Exception as e:
                print(f"[CoreMemory] Proactive consolidate failed (non-fatal): {e}")
        return {"ok": True, "new_len": new_len}

    # Hard limit exceeded — full path.
    if auto_consolidate:
        print(f"[CoreMemory] Block '{label}' full ({len(current)}/{limit} chars), "
              f"attempting hard auto-consolidation...")
        consolidate_result = consolidate(label)
        if consolidate_result.get("ok"):
            # Retry once without recursion guard
            return append(label, content, auto_consolidate=False)
        else:
            print(f"[CoreMemory] Auto-consolidation failed: {consolidate_result.get('error')}")

    with _lock:
        data = _load()
        block = data.get(label, {})
        current = block.get("value", "")
        limit = block.get("limit", DEFAULT_BLOCK_LIMIT)
    return {
        "ok": False,
        "error": f"Block full ({len(current)}/{limit} chars, need {len(content)} more)",
        "current_value": current,
        "chars_remaining": limit - len(current),
    }


def consolidate(label: str, target_ratio: float = TARGET_RATIO) -> dict:
    """Compress a core memory block to ~target_ratio of its limit via LLM.

    Reads the current block content, asks the cheap memory-tier LLM to
    rewrite it into a more concise version, and replaces the block value.

    Args:
        label: Block label ("human" or "persona")
        target_ratio: Target size as fraction of limit (default TARGET_RATIO = 60%)

    Returns: {"ok": True, "old_len": int, "new_len": int} on success
    """
    with _lock:
        data = _load()
        if label not in data:
            return {"ok": False, "error": f"Unknown block: {label}"}
        block = data[label]
        current = block.get("value", "")
        limit = block.get("limit", DEFAULT_BLOCK_LIMIT)

    if not current.strip():
        return {"ok": False, "error": "Block is empty, nothing to consolidate"}

    target_chars = int(limit * target_ratio)
    if len(current) <= target_chars:
        return {"ok": True, "old_len": len(current), "new_len": len(current),
                "message": "Block already within target size"}

    # Call cheap LLM (memory tier) to consolidate.
    # We deliberately use the memory tier (not chat) because consolidation
    # is a background routine and shouldn't compete with the chat-agent
    # response budget.
    try:
        from prompt import _call_llm_text
        from character import get_config
        cfg = get_config()

        if label == "human":
            extra_rule = (
                "- This is a profile of the user. **Do not** write structured fields like "
                "name/occupation/schedule here (these are stored separately in identity); "
                "keep only **narrative** dynamic profiles (personality tendencies, "
                "recent situation, relationship network, preference habits, etc.)."
            )
        elif label == "persona":
            extra_rule = (
                f"- This is a profile of {cfg.name} (yourself). Preserve experiences "
                "shared with the user and the evolution of your feelings about this "
                "relationship. Remove outdated transient emotions."
            )
        else:
            extra_rule = ""

        prompt = f"""You are {cfg.name}'s memory organization assistant. Below is the \"{label}\" block in {cfg.name}'s core memory.

This memory block has reached {len(current)} characters (soft limit {target_chars}, hard limit {limit}).
Please compress it to within {target_chars} characters while retaining all important information, removing duplicate, outdated, and low-information content.

General rules:
- Merge duplicate entries
- Remove outdated temporary states (e.g. bad mood a day or two ago that has passed)
- Maintain original format (one entry per line)
- Output the compressed text directly without any explanatory text
{extra_rule}

[Current Content]
{current}"""

        compressed = _call_llm_text(
            prompt, "Please output the compressed text.",
            temperature=0.1, max_tokens=10000, tier="memory",
            call_label=f"CoreMemoryConsolidate:{label}",
        )
    except Exception as e:
        return {"ok": False, "error": f"LLM consolidation failed: {e}"}

    if not compressed or not compressed.strip():
        return {"ok": False, "error": "LLM returned empty consolidation result"}

    compressed = compressed.strip()
    if len(compressed) > limit:
        compressed = compressed[:target_chars]

    # Replace the block value
    with _lock:
        data = _load()
        old_len = len(data[label].get("value", ""))
        data[label]["value"] = compressed
        _save(data)

    new_len = len(compressed)
    print(f"[CoreMemory] Consolidated '{label}': {old_len} → {new_len} chars "
          f"({new_len * 100 // limit}% of limit)")
    return {"ok": True, "old_len": old_len, "new_len": new_len}


def initialize_from_existing() -> dict:
    """Seed core memory from existing data and fix stale config.

    - Migrates old limits (e.g. 2000) to current DEFAULT_BLOCKS limits
    - Re-seeds blocks whose content references a different character name
    - Only fills truly empty blocks on first run
    """
    with _lock:
        data = _load()
        actions = []

        from character import get_config
        cfg = get_config()

        # Migrate stale limits
        for label, defaults in DEFAULT_BLOCKS.items():
            block = data.get(label)
            if block and block.get("limit", 0) < defaults["limit"]:
                block["limit"] = defaults["limit"]
                data[label] = block
                actions.append(f"{label} limit updated to {defaults['limit']}")

        # Check if persona block references a different character (stale from old soul.md)
        persona_block = data.get("persona", DEFAULT_BLOCKS["persona"].copy())
        persona_value = persona_block.get("value", "").strip()
        needs_reseed = (
            not persona_value
            or (cfg.name not in persona_value and len(persona_value) < 500)
        )
        if needs_reseed:
            persona_seed = (
                f"I am {cfg.name}.\n"
                f"Just met the user, still getting to know each other, but looking forward to it.\n"
                f"My role: companionship, remembering important things, sincerely caring about each other.\n"
            )
            persona_block["value"] = persona_seed
            data["persona"] = persona_block
            actions.append("persona reseeded for current character")

        # Seed human block if empty
        human_block = data.get("human", DEFAULT_BLOCKS["human"].copy())
        if not human_block.get("value", "").strip():
            import memory
            human_seed = ""
            for filename in ["profile.md", "preferences.md", "about.md"]:
                content = memory.read_file(f"self/{filename}")
                if content:
                    human_seed += content.strip() + "\n"
            if not human_seed:
                human_seed = "(Not yet familiar with the user, waiting to learn through conversation)\n"
            human_block["value"] = human_seed[:human_block.get("limit", 100000)]
            data["human"] = human_block
            actions.append("human seeded")

        if actions:
            _save(data)

        return {"actions": actions, "blocks": {k: len(v.get("value", "")) for k, v in data.items()}}


def format_for_context() -> str:
    """Format core memory blocks as XML for system prompt injection."""
    blocks = get_all_blocks()
    parts = []
    for label, value in blocks.items():
        if value.strip():
            parts.append(f'<core_memory label="{label}">\n{value}\n</core_memory>')
        else:
            parts.append(f'<core_memory label="{label}">\n[empty]\n</core_memory>')
    return "\n".join(parts)
