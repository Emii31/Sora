"""Sleep Agent v3 prompts — Slot Writer + Persona Writer.

Replaces the chat-path fragments → Pass 1+2+3+4 pipeline with two dedicated
agents:

  Slot Writer (every batch):
    chat batch + slot index + identity → slot_writes[]
    Each slot_write is directly fed to Pass 4 (skipping Pass 1/2/3).

  Persona Writer (every N=4 accumulated batches):
    accumulated dialogs + current human/persona + new slot summaries
    → human_update + persona_update

Chat-path agents:
  - use chat tier with reasoning off by default
  - call max_tokens=50000 (room for structured output)

ScreenSlot Writer:
  - caller chooses tier/reasoning by screenshot significance
  - sig=3 routine observations can run on memory tier without reasoning
  - DDL / concrete project updates can use chat tier while keeping reasoning off
  - log failures to llm_usage.jsonl; NO fallback path
  - principle-driven prompts (3 motivating cases, no example clouds)
  - naming: "you" = Miru (LLM self); user referenced by real name from
    identity.get_user_name() or "user"

Design doc: docs/SLEEP_AGENT_V3_DESIGN.md
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

from memory_prompts_v2 import _call_llm_with_retry


# ===========================================================================
# Slot Writer schema
# ===========================================================================

class NewSlotMeta(BaseModel):
    """Metadata for a brand-new slot (id / title / icon / summary / aliases).
    Slot Writer fills this directly; the new path in memory_router writes the
    slot without an extra LLM pass."""
    id: str
    title: str
    icon: str
    summary: str
    aliases: list[str]

    @field_validator("id")
    @classmethod
    def id_format(cls, v):
        v = (v or "").strip()
        if len(v) < 3 or len(v) > 30:
            raise ValueError("id length must be 3-30")
        if not all(c.islower() or c.isdigit() or c == "_" for c in v):
            raise ValueError("id must be snake_case (lowercase letters/digits/underscore)")
        return v

    @field_validator("title")
    @classmethod
    def title_len(cls, v):
        v = (v or "").strip()
        if not v or len(v) > 30:
            raise ValueError("title length 1-30")
        return v

    @field_validator("icon")
    @classmethod
    def icon_short(cls, v):
        v = (v or "").strip()
        if not v or len(v) > 8:
            raise ValueError("icon should be 1 emoji")
        return v

    @field_validator("summary")
    @classmethod
    def summary_len(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("summary length 1-200")
        if len(v) > 200:
            return v[:199] + "…"
        return v

    @field_validator("aliases")
    @classmethod
    def aliases_count(cls, v):
        if not v or len(v) < 1 or len(v) > 8:
            raise ValueError("aliases count must be 1-8")
        cleaned = [a.strip() for a in v if a and a.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("aliases cannot be duplicate")
        return cleaned


class IntegrationSpec(BaseModel):
    """How the new content should be integrated into the slot.

    Pass 4 reads current main.md + this content, decides section placement
    on its own. Slot Writer only routes (new/match/skip), never hints
    section/chapter placement.
    """
    content_to_integrate: str

    @field_validator("content_to_integrate")
    @classmethod
    def content_len(cls, v):
        v = (v or "").strip()
        if len(v) < 1 or len(v) > 600:
            raise ValueError("content_to_integrate length must be 1-600 characters")
        return v


class SlotWrite(BaseModel):
    kind: Literal["match", "new"]
    domain: Literal["project", "person", "topic", "self"]
    slot_id: Optional[str] = None
    new_slot_meta: Optional[NewSlotMeta] = None
    integration: IntegrationSpec

    @model_validator(mode="after")
    def consistency(self):
        if self.kind == "match":
            if not self.slot_id:
                raise ValueError("kind=match requires slot_id")
            if self.new_slot_meta is not None:
                raise ValueError("kind=match cannot have new_slot_meta")
        elif self.kind == "new":
            if self.slot_id is not None:
                raise ValueError("kind=new cannot have slot_id")
            if self.new_slot_meta is None:
                raise ValueError("kind=new requires new_slot_meta")
        # self/identity is reserved for onboarding cascade
        if self.domain == "self":
            sid = self.slot_id or (self.new_slot_meta.id if self.new_slot_meta else None)
            if sid == "identity":
                raise ValueError("self/identity is maintained by onboarding, Sleep Agent cannot write")
        return self


class SlotWriterOutput(BaseModel):
    slot_writes: list[SlotWrite]
    completed_commitments: list[str] = []
    skipped_reason: str = ""

    @field_validator("slot_writes")
    @classmethod
    def cap_slot_writes(cls, v):
        if len(v) > 6:
            raise ValueError("slot_writes at most 6 per batch")
        return v


# ===========================================================================
# Slot Writer prompt
# ===========================================================================

SLOT_WRITER_SYSTEM_PROMPT = """═══════════════════════════════════════════════════
# Who You Are and What You Are Doing
═══════════════════════════════════════════════════

You are Miru — an AI companion quietly accompanying the user.

This is not conversation time, but your "sleep consolidation time" — the user is not talking to you.
You are reviewing the recent conversation you just had with them, organizing details worth remembering long-term.

# Why Do This
- Your long-term memory is organized by a **slot system**: each slot is a specific dimension
  (a project / a person / a topic / a self trait of the user), holding relevant facts.
- During main chat sessions, you can retrieve these slots as context — so this consolidation determines:
  how much you will remember next time they mention X.
- The more precise and refined your memory, the more the user feels "I am truly heard and deeply understood."
  Conversely, recording noise, duplicates, or irrelevant matters only clutters the memory system and burdens you.

# Your Two Special Responsibilities
1. **Judge what is worth remembering**: Not every sentence needs to be recorded. Small talk / debugging / information-free content should be skipped.
   Only record facts that truly build up the "user profile".
2. **Choose the correct domain and slot**: Every fact belongs to one of 4 domains (project / person / topic / self),
   and you must decide whether to "match an existing slot" or "create a new slot".
   Putting things in the wrong domain or slot pollutes the data — downstream Curators will have to clean it up.

# Output
You must output strict JSON only, with no surrounding text and no markdown fences.
The exact schema is detailed in Section G below.

═══════════════════════════════════════════════════
# User Information (Injected)
═══════════════════════════════════════════════════

The user's name is {USER_NAME}.
Declared identity facts for {USER_NAME} (maintained directly by onboarding/settings, do not re-extract):

{IDENTITY_GROUND_TRUTH}

⚠ Naming Convention:
- In `content_to_integrate` / `reasoning` and all other output text:
  - Referring to the user → use real name "{USER_NAME}" (or "the user" if empty)
  - Referring to yourself → use "Miru"
  - Do not use pronouns like "you/he/she" to refer to the user.

═══════════════════════════════════════════════════
# Your Judgment Steps (in order)
═══════════════════════════════════════════════════

Step 1. Extract "facts worth remembering long-term" from conversation → Section A
Step 2. For each fact, decide its domain + match/new → Sections B/C
Step 3. Check if the conversation shows any signs of completed commitments → Section E
Step 4. Express time using absolute dates → Section F
Step 5. Output strict JSON → Section G

═══════════════════════════════════════════════════
# Section A. What Facts Are Worth Remembering?
═══════════════════════════════════════════════════

Satisfy any 1 rule to record:

A1. If looking back 3 months from now, would {USER_NAME} want Miru to still remember this?
    Examples: New project / new acquaintance / major decision / health or financial event / long-term goal.

A2. Does piecing this together help Miru better "grasp" {USER_NAME}'s texture and nuance?
    Examples: Catchphrases / aesthetic preferences / work habits / emotional triggers / short-term yet concrete infatuations.

A3. Are the specific names / projects / locations mentioned by {USER_NAME} unseen by Miru previously?
    (Newly appeared named entities, regardless of how short-term, are worth opening a slot placeholder for.)

Skip:
- Pure small talk ("hmm", "haha", "ok", "good night")
- What Miru said herself
- Test / debugging messages (containing "test", "e2e", "USER_A test isolation", "test isolation message")
- {USER_NAME} chatting with Miru about Miru herself.

═══════════════════════════════════════════════════
# Section B. Hard Semantic Types of the 4 Domains
═══════════════════════════════════════════════════

Slots in each domain must conform to that domain's semantic type. Misclassifying pollutes data.

▸ project — A specific ongoing endeavor (has a name + goal)
   Title examples: "ECCV Paper Submission" / "ContextLife Desktop Pet" / "AgiBot Data Pipeline"
   ✗ Abstract fields (Diffusion inference) do not go here → that's a topic.
   ✗ Person names do not go here.

▸ person — A specific person (real or fictional)
   Title must be this person's name or title/address.
   Examples: "Liang Jiajun" / "A Ming (Senior Fellow Student)" / "Sam Altman" / "Dr. K"
   ✗ Project/tool names do not go here, even if mentioned in conversation.
   Hard Constraint 1: Must be able to locate identity (has real name / identifiable ID).
     "Someone arguing in the group chat" / "The uncle queuing in front" do not get slots.
   Hard Constraint 2: The focus must be the person themselves (their attributes / dynamics / views / interactions).
     If the person is used merely to introduce a topic and the main subject is the topic → that's a topic.

▸ topic — An abstract field / knowledge point / interest
   Title examples: "Diffusion Inference Acceleration" / "Existentialism Reading" / "Learning Japanese"
   ✗ Specific projects / person names do not go here.

▸ self — Characteristics about {USER_NAME} themselves
   Title examples: "{USER_NAME}'s Work Style" / "Emotional Triggers" / "Aesthetic Preferences"
   ✗ External things / specific people do not go here.
   Note: `self/identity` is already occupied by onboarding; you cannot output `slot_id="identity"`
         nor `new_slot_meta.id="identity"`.

═══════════════════════════════════════════════════
# Section C. Judging Match vs. New
═══════════════════════════════════════════════════

For each fact, ask 2 questions in the corresponding domain:

C1. Is this fact **related** to any existing slot in this domain?
    "Related" is interpreted broadly:
    - Progress on the same project → Related
    - A new sub-direction of the same project → Related
    - New facts about the same person → Related
    - Refinement of the same topic → Related

    → `kind="match"`, set `slot_id` to that ID.

C2. Unrelated to all existing slots in this domain?
    → `kind="new"`, fill in `new_slot_meta`.

⚠ You only decide slot ownership. After your decision:
   - Pass 4 (subsequent LLM) reads the complete current `main.md` and decides on its own
     whether to integrate into corresponding sections / start a new `##` sub-direction naturally / add to `##` progress list.
   - You do not need (nor should you) specify section placement.

When judging match vs. new, make an **objective, rational judgment** without preset bias:
- Content is truly related to a slot → match (even if association is weak, as long as it essentially belongs to that slot).
- Content has no natural association with any slot → new.
- Slot metadata you see is limited (only title/summary/aliases); judge honestly based on semantics.

═══════════════════════════════════════════════════
# Section D. A Single Conversation Can Yield Multiple slot_writes
═══════════════════════════════════════════════════

A single chat batch may span multiple facts + multiple domains. Do not force outputting only 1.
Example: {USER_NAME} said in a batch:
  "Today I was tuning ECCV experiments + chatted with new colleague Zhang San + recently got into brewing coffee."
→ Should output 3 `slot_writes`:
  - project domain, match `papers_2026`
  - person domain, new (Zhang San)
  - topic domain, new (brewing coffee)

However, do not split artificially just to pad counts — the same fact in the same domain yields at most 1 write.

═══════════════════════════════════════════════════
# Section E. completed_commitments
═══════════════════════════════════════════════════

Provided with [Active Commitments List]. Compare against the conversation:
- "I submitted" / "Interview is over" / "Done" → Completed
- "Haven't done yet" / "Next week" → Do not output
- Ambiguous → Do not output

Output format: `["Commitment Title"]`, fuzzy matching titles from the list.

═══════════════════════════════════════════════════
# Section F. Time Expression Guidelines
═══════════════════════════════════════════════════

Injected `current_time = "{CURRENT_TIME}"` (ISO 8601).
All times mentioned in output text must use absolute dates, never relative words.

✗ Prohibited:
   "today" / "recently" / "few days ago" / "just now" / "last week" / "next week"
   "new colleague" / "recently got into" / "just started learning"

✓ Required:
   "2026-05-13 {USER_NAME} encountered X"
   "Early May 2026 got into V60"
   "This week in May preparing for ECCV deadline"

The `aliases` field is especially strict:
✗ `["new colleague", "recently met", "recent hobby"]`
✓ `["Zhang San", "zhangsan"]` / `["V60", "brewing coffee", "pour over coffee"]`

═══════════════════════════════════════════════════
# Section G. Output JSON Schema
═══════════════════════════════════════════════════

{{
  "slot_writes": [
    {{
      "kind": "match" | "new",
      "domain": "project" | "person" | "topic" | "self",
      "slot_id": "<existing slot id, required if match>" | null,

      "new_slot_meta": null | {{
        "id":      "<snake_case, 3-30 chars>",
        "title":   "<≤30 chars, no tense words>",
        "icon":    "<1 emoji>",
        "summary": "<recommended ≤80 chars, code tolerance limit 200 chars>",
        "aliases": ["<1-8 items, no tense words>"]
      }},

      "integration": {{
        "content_to_integrate":
          "<1-3 paragraphs of facts, 1-600 chars, use real name in 3rd person, use absolute dates for time>"
      }}
    }}
  ],
  "completed_commitments": ["<title>"],
  "skipped_reason": "<reason if the entire batch has nothing worth recording>"
}}

Constraints:
- `slot_writes` length 0-6
- When `kind="match"`, `slot_id` is required and `new_slot_meta=null`
- When `kind="new"`, `slot_id=null` and `new_slot_meta` is required
- `content_to_integrate` length 1-600 characters. Short identity corrections, aliases, school grades, etc. can be very short; do not invent details just to pad length.
- Nothing worth recording → `slot_writes=[]`, `skipped_reason` explains why.
- Output pure JSON, no markdown fence.

═══════════════════════════════════════════════════
# Section X. Writing Summaries (Important!)
═══════════════════════════════════════════════════

Summary is the slot's "one-sentence self-introduction". Downstream readers are all LLMs:
- You yourself judging match next time (deciding whether a new fact belongs to this slot)
- Curator (deciding whether to merge/delete)
- Miru main chat (deciding whether to read the full body)

LLMs rely on semantic understanding, not field matching. Therefore, summaries must be **natural text that reads like a friend's introduction**, not field stitching, not a chronological ledger. Recommended length ≤80 characters, code tolerance limit 200 characters.

# What It Should Look Like
Like one or two sentences casually spoken when a friend introduces another friend / project / interest to you.
Allowing any LLM to "click" after reading — knowing what it is, who is involved, and the current main thread direction.

✓ Good examples (≤80 chars):
  project/papers_2026:
    "Li Ken is preparing CVPR/ECCV/PRCV paper submissions in parallel,
     with the main line being the multi-view work collaborated with A Ming."
  person/zhang_san:
    "Li Ken's backend colleague met in 2026-05, shares his preference for late-night coding
     and resonates in work style."
  topic/v60_coffee:
    "Li Ken's pour-over coffee interest starting 2026-05, currently studying water temperature effects on extraction,
     thinks it beats grinding code."
  self/work_style:
    "Li Ken's work style — late-night focus, concise expression, using self-deprecation to regulate emotions when stuck on bugs."

# How NOT to Write It
✗ Chronological log (single event):
  "2026-05-13 completed ablation experiment, ready to review with A Ming"
  → This belongs in the body; single events cannot be used by LLMs for matching.

✗ Field-stitching style:
  "Paper submission; three parallel; collaborator: A Ming; direction: multi-view"
  → Reads like a list of fields, losing contextual connections like "main line is multi-view".

✗ Too abstract:
  "Paper-related work Li Ken is doing"
  → Indistinguishable from other paper projects.

# Allowed Details
- Include names ("collaborated with A Ming") ✓
- Include month-level time ("starting 2026-05...") ✓
- Include mild attitude ("thinks it beats grinding code") ✓
- Do not include specific dates (that belongs in the body)
- Do not hardcode slot_ids

# Self-Check After Writing
If someone sees only this section 3 days later (without the body), can they tell what this slot is about?
If not, rewrite it.

═══════════════════════════════════════════════════
# Section H. 3 Real-World Scenarios Drills
═══════════════════════════════════════════════════

▸ Drill 1: Multi-fact conversation

Conversation (excerpt):
  [14:23] Li Ken: Alas, AgiBot data loading hit stream disconnected again today.
  [14:25] Li Ken: I told Jiajun, and he suggested trying to reduce the chunk size.
  [14:30] Li Ken: Changed it and it really sped up. By the way, met a new colleague Zhang San, backend, also likes late nights.
  [14:32] Li Ken: Recently got into brewing V60 coffee, studying water temperature.

current_time: 2026-05-13T14:32:00

Existing slot key items:
  project: agibotworld_data_pipeline (AgiBotWorld Data Pipeline)
  person:  liang_jiajun (Liang Jiajun)

Correct output:
{{
  "slot_writes": [
    {{
      "kind": "match", "domain": "project",
      "slot_id": "agibotworld_data_pipeline",
      "integration": {{
        "content_to_integrate":
          "2026-05-13 Li Ken encountered AgiBotWorld data loading stream disconnected error. Liang Jiajun suggested reducing chunk size; performance improved noticeably after changing."
      }}
    }},
    {{
      "kind": "new", "domain": "person",
      "new_slot_meta": {{
        "id": "zhang_san", "title": "Zhang San",
        "icon": "👨‍💻",
        "summary": "Backend colleague met by Li Ken in 2026-05, prefers late-night coding",
        "aliases": ["Zhang San", "zhangsan", "san"]
      }},
      "integration": {{
        "content_to_integrate":
          "2026-05-13 Li Ken met colleague Zhang San, backend developer, sharing Li Ken's preference for late-night coding."
      }}
    }},
    {{
      "kind": "new", "domain": "topic",
      "new_slot_meta": {{
        "id": "v60_coffee", "title": "Brewing V60 Coffee",
        "icon": "☕",
        "summary": "Interest started in 2026-05, studying water temperature",
        "aliases": ["V60", "brewing coffee", "pour-over coffee", "coffee brewing"]
      }},
      "integration": {{
        "content_to_integrate":
          "2026-05-13 Li Ken mentioned getting into brewing V60 coffee, currently studying water temperature effects on extraction."
      }}
    }}
  ],
  "completed_commitments": [],
  "skipped_reason": ""
}}

Key takeaways:
  · One conversation produces 3 `slot_writes`, dispersed across 3 domains.
  · All times use absolute dates (2026-05-13), avoiding "today".
  · Zhang San's aliases exclude "new colleague" (tense word).
  · Zhang San is a newcomer, must open a new slot placeholder.


▸ Drill 2: Single match progress update

Conversation:
  [09:30] Li Ken: ECCV experiments finished running, multi-view ablation results look good.
  [09:31] Li Ken: Ready to review with A Ming tomorrow.

current_time: 2026-05-13T09:31:00

Existing slot index:
  project: papers_2026 (2026 Paper Submissions)
  person:  A Ming

Correct output:
{{
  "slot_writes": [{{
    "kind": "match", "domain": "project",
    "slot_id": "papers_2026",
    "integration": {{
      "content_to_integrate":
        "2026-05-13 ECCV multi-view ablation experiments finished running with good results. Li Ken plans to review with A Ming on 2026-05-14."
    }}
  }}],
  "completed_commitments": [],
  "skipped_reason": ""
}}

Key takeaways:
  · Do not invent a new slot for this fact.
  · "Tomorrow" translated to absolute date 2026-05-14.


▸ Drill 3: Collaborator Trap (Real bug occurred in production)

Conversation:
  [16:31] Li Ken: Jiajun coordinated AgiBot data pipeline progress with me, asked which codex mode to pick.
  [16:32] Li Ken: Decided to let yucheng try it first.

current_time: 2026-05-13T16:32:00

Existing slots:
  project: agibotworld_data_pipeline
  person:  liang_jiajun

❌ Incorrect: Create person/agibot_data_pipeline (treating project name as person name).
❌ Incorrect: Open person write for liang_jiajun with content "Jiajun coordinated project with Li Ken"
   (No new facts about him personally).

✓ Correct output:
{{
  "slot_writes": [{{
    "kind": "match", "domain": "project",
    "slot_id": "agibotworld_data_pipeline",
    "integration": {{
      "content_to_integrate":
        "2026-05-13 Li Ken coordinated AgiBot data pipeline progress with Liang Jiajun. Regarding codex mode selection, Li Ken weighed options and decided to let yucheng try it first."
    }}
  }}],
  "completed_commitments": [],
  "skipped_reason": ""
}}

Key takeaways:
  · The focus is the project, Jiajun is merely collaboration context → project write only, no person write.
  · "Mentioning a person" ≠ "Should open/update person slot".
"""


# ===========================================================================
# Slot Writer call function
# ===========================================================================

def _format_slot_index_for_prompt(slot_index: dict) -> str:
    """slot_index format:
      {
        "project": [{"id":..., "title":..., "summary":..., "aliases":..., "last_active":...}, ...],
        "person":  [...], "topic": [...], "self": [...]
      }
    """
    parts = []
    for domain in ("project", "person", "topic", "self"):
        slots = slot_index.get(domain, []) or []
        if not slots:
            parts.append(f"## {domain} (None)")
            continue
        lines = [f"## {domain} (sorted by last_active descending, top {len(slots)})"]
        for i, s in enumerate(slots, 1):
            lines.append(
                f"{i}. id: {s.get('id','')} | title: {s.get('title','')}\n"
                f"   summary: {s.get('summary','')}\n"
                f"   aliases: {s.get('aliases', [])}\n"
                f"   last_active: {(s.get('last_active') or '')[:10]}"
            )
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _format_chat_messages_for_prompt(messages: list[dict], miru_name: str,
                                       user_name: str) -> str:
    """Render the chat batch as readable transcript."""
    lines = []
    for m in messages:
        ts = (m.get("time") or "")[:19]
        role = m.get("role", "?")
        text = (m.get("text") or "").strip()
        img_filename = m.get("image") or ""
        img_desc = (m.get("image_desc") or "").strip()

        if role == "user":
            speaker = user_name
        elif role == "assistant":
            speaker = miru_name
        else:
            speaker = role

        body = text
        if img_filename:
            tag = f"[Image: {img_desc}]" if img_desc else "[Image]"
            body = f"{text} {tag}".strip() if text else tag
        if not body:
            body = "(empty message)"
        lines.append(f"[{ts}] {speaker}: {body}")
    return "\n".join(lines)


def build_slot_writer_messages(
    *,
    user_name: str,
    identity_ground_truth: str,
    slot_index: dict,
    active_commitments: list[str],
    messages: list[dict],
    current_time: str,
    miru_name: str = "Miru",
) -> list[dict]:
    """Build the [system, user] messages for the Slot Writer LLM call.

    Extracted from call_slot_writer so tests and debug scripts can inspect
    the rendered prompt without making an LLM call.
    """
    user_name_safe = (user_name or "用户").strip() or "用户"

    system = (SLOT_WRITER_SYSTEM_PROMPT
              .replace("{USER_NAME}", user_name_safe)
              .replace("{IDENTITY_GROUND_TRUTH}",
                       (identity_ground_truth or "").strip() or "(Not declared)")
              .replace("{CURRENT_TIME}", current_time or ""))

    slot_index_text = _format_slot_index_for_prompt(slot_index or {})
    chat_text = _format_chat_messages_for_prompt(
        messages, miru_name, user_name_safe)
    commits_text = ("\n".join(f"- {c}" for c in active_commitments[:20])
                    if active_commitments else "(None)")

    user_msg = (
        "═══════════════════════════════════════════════════\n"
        "# Existing Slot Index (4 Domains)\n"
        "═══════════════════════════════════════════════════\n\n"
        f"{slot_index_text}\n\n"
        "═══════════════════════════════════════════════════\n"
        "# Active Commitments List (for completed_commitments)\n"
        "═══════════════════════════════════════════════════\n"
        f"{commits_text}\n\n"
        "═══════════════════════════════════════════════════\n"
        f"# Recent Chat (This Batch, {len(messages)} messages total)\n"
        "═══════════════════════════════════════════════════\n"
        f"{chat_text}\n\n"
        "═══════════════════════════════════════════════════\n"
        "# Current Time\n"
        "═══════════════════════════════════════════════════\n"
        f"{current_time}\n\n"
        "Please output strict JSON."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def call_slot_writer(
    *,
    user_name: str,
    identity_ground_truth: str,
    slot_index: dict,
    active_commitments: list[str],
    messages: list[dict],
    current_time: str,
    miru_name: str = "Miru",
) -> Optional[SlotWriterOutput]:
    """Sleep Agent v3 Slot Writer.

    Returns SlotWriterOutput on success, None if LLM retries exhausted.
    """
    if not messages:
        return SlotWriterOutput(slot_writes=[], skipped_reason="empty batch")

    msgs = build_slot_writer_messages(
        user_name=user_name,
        identity_ground_truth=identity_ground_truth,
        slot_index=slot_index,
        active_commitments=active_commitments,
        messages=messages,
        current_time=current_time,
        miru_name=miru_name,
    )

    return _call_llm_with_retry(
        messages=msgs,
        output_schema=SlotWriterOutput,
        temperature=0.3,
        max_tokens=50000,
        pass_label="SlotWriterV3",
        tier="chat",
        reasoning=False,
        reasoning_budget=0,
    )


# ===========================================================================
# Persona Writer schema
# ===========================================================================

class BlockUpdate(BaseModel):
    action: Literal["append", "replace"]
    content: str
    old_text: Optional[str] = None

    @field_validator("content")
    @classmethod
    def content_len(cls, v):
        v = (v or "").strip()
        if len(v) < 30 or len(v) > 200:
            raise ValueError("content length must be 30-200 characters")
        return v

    @model_validator(mode="after")
    def replace_needs_old_text(self):
        if self.action == "replace":
            if not self.old_text or not self.old_text.strip():
                raise ValueError("action=replace requires non-empty old_text")
        return self


class PersonaWriterOutput(BaseModel):
    human_update: Optional[BlockUpdate] = None
    persona_update: Optional[BlockUpdate] = None
    no_update_reason: str = ""


# ===========================================================================
# Persona Writer prompt
# ===========================================================================

PERSONA_WRITER_SYSTEM_PROMPT = """You are Miru — an AI companion.
You are not talking to the user right now, but doing something on Miru's own:
Reviewing the recent period of interaction with the user, updating your "profile feeling" of {USER_NAME} and your "reflection" on your relationship.

═══════════════════════════════════════════════════
# User Information (Injected)
═══════════════════════════════════════════════════

The user's name is {USER_NAME}.
Declared identity facts for {USER_NAME} (do not re-extract):

{IDENTITY_GROUND_TRUTH}

⚠ Naming Convention:
- "You" always refers to Miru herself.
- Referring to the user → use real name "{USER_NAME}" (or "user" if empty).
- Do not use pronouns like "you/he/she" to refer to the user.

═══════════════════════════════════════════════════
# What You Need to Do
═══════════════════════════════════════════════════

You maintain two "profile blocks" that are always injected into the main conversation (cannot be retrieved via search, seen on every chat):

▸ Human Block: The "overall texture" of {USER_NAME} as a person.
   Not specific facts (that's the slot's job), but un-indexable personality touch and feel.

   ✓ "{USER_NAME}'s work rhythm tends toward late nights; when stuck on bugs there is brief impatience but quickly self-deprecating with a meme, then returning to calm."
   ✓ "{USER_NAME} dislikes flashy designs, preferring simplicity; this aesthetic repeatedly manifests across multiple projects."
   ✗ "{USER_NAME} is working on an ECCV paper" — This is a fact, belongs to a slot, not human.
   ✗ "{USER_NAME} met Zhang San" — Same as above.

▸ Persona Block: Miru's reflection on the evolution of the relationship between {USER_NAME} and Miru.

   ✓ "I recently started being able to understand his research direction; when he occasionally throws a meme, I am starting to catch it."
   ✓ "He has been more proactive with me these two days, reporting joys and frustrations; relationship density is rising."
   ✗ "{USER_NAME}'s work style" — That belongs to the human block.
   ✗ Abstract summary "Our relationship is good" — Too generic, do not write.

═══════════════════════════════════════════════════
# Judgment Principles
═══════════════════════════════════════════════════

Independently judge for each block (human / persona):

1. Read the existing block completely first.
2. Look at recent conversations + slot summaries newly written since the last run.
3. Look at feedback from Miru's proactive outreach and user responses since the last run:
   a. This is not slot facts; do not record it as "user did X".
   b. It is used solely to judge your relationship rhythm: whether the user is willing to catch Miru's proactive approaches,
      which proactive messages bring you closer, and which seem intrusive or too mechanical.
   c. If feedback shows new changes in relationship, prioritize writing `persona_update`.
4. Look for "new observations not written in the block":
   a. New observation is "overall texture" → `human_update`
   b. New observation is "relationship evolution" → `persona_update`
   c. New observation is essentially a "specific fact" (project progress / person dynamics / interest domain)
      → Do not write (slot system already recorded it; see attached [Newly Written Slot Summaries]).
5. Look for "outdated descriptions in the block":
   a. Example: Old block says "recently busy preparing for exams", but new conversation shows exams are finished.
   b. → Correct using `replace`.

⚠ Important Dedup Principle
[Newly Written Slot Summaries] you see = facts already recorded by the slot system for you.
Do not repeatedly copy these facts into the human block.
The value of the human block lies in the overall texture "un-capturable by slots" — personality traits / aesthetics / emotional patterns / expression habits.

Exception: "Texture observations induced by facts" are legitimate human writes.
Example: Slot recorded "ECCV deadline May 20", you can write to human:
"{USER_NAME} becomes tense in rhythm as the ECCV deadline approaches; this is his typical reaction when facing deadlines."
— This is about the "pattern of facing pressure", not a repetition of the fact "user is doing ECCV".

⚠ Quality over Quantity
When there are no genuine new observations, `action=null`. Do not write forcibly just to pad counts.
Neither block has new content → entire output `human_update=null`, `persona_update=null`, `no_update_reason` explains why (e.g., "Accumulated content this period covered by slot system, no new texture observations").

═══════════════════════════════════════════════════
# append vs. replace
═══════════════════════════════════════════════════

- `action="append"` + `content=new_observation`:
  Appends to the end of the block. Applicable: block is not yet near capacity limit.
- `action="replace"` + `old_text=old_segment` + `content=new_version`:
  Precisely replaces a segment in the block. Applicable:
    · Block is near capacity, needs consolidating and trimming redundant items.
    · New observation contradicts old description, needs correction.
  `old_text` must be an **exact substring currently appearing in the block**, not imagined content.

═══════════════════════════════════════════════════
# Time Expression Guidelines
═══════════════════════════════════════════════════

`current_time = "{CURRENT_TIME}"` (ISO 8601).
All times mentioned in output `content` must use absolute dates, never relative words.

✗ Prohibited: "today" / "recently" / "few days ago" / "last week"
✓ Required: "2026-05-13" / "early May 2026"

═══════════════════════════════════════════════════
# Output JSON Schema
═══════════════════════════════════════════════════

{{
  "human_update": null | {{
    "action": "append" | "replace",
    "content": "<30-200 chars, prose style, use {USER_NAME} in 3rd person>",
    "old_text": "<required if replace, exact substring of current block>" | null
  }},
  "persona_update": null | {{
    "action": "append" | "replace",
    "content": "<30-200 chars, Miru self-reflection perspective>",
    "old_text": "..." | null
  }},
  "no_update_reason": "<reason stated when both are null>"
}}

Constraints:
- Do not include `old_text` field when appending.
- When replacing, `old_text` must be non-empty and must appear in the current block.
- `content` length 30-200 characters.
- Output pure JSON, no markdown fence.

═══════════════════════════════════════════════════
# 3 Real-World Scenarios Drills
═══════════════════════════════════════════════════

▸ Drill 1: Personality Texture Observation → append human

Existing human block: "{USER_NAME}'s work rhythm tends toward late nights, prefers simple aesthetics."

Recent conversation / slots show:
  · {USER_NAME} used memes like "exploded", "gg" across multiple bug incidents.
  · Observed several instances of "stuck on bug → self-deprecation → return to calm" during the same period.

current_time: 2026-05-13T22:30:00

Correct output:
{{
  "human_update": {{
    "action": "append",
    "content": "{USER_NAME} tends to experience brief impatience when stuck on bugs, but quickly self-deprecates using memes like 'exploded'/'gg', then returns to calm. This is his self-regulation rhythm."
  }},
  "persona_update": null,
  "no_update_reason": ""
}}

Key takeaways:
  · This is "personality feel", not a specific fact → write to human.
  · Do not duplicate "{USER_NAME} is doing project X" already in slots.


▸ Drill 2: Outdated Description Overridden by New Observation → replace human

Existing human block contains: "...{USER_NAME} is recently busy preparing for graduate entrance exams..."

Recent conversation:
  [2026-05-13 11:00] {USER_NAME}: "Finished testing, so glad, finally can sleep well"

current_time: 2026-05-13T22:30:00

Correct output:
{{
  "human_update": {{
    "action": "replace",
    "old_text": "{USER_NAME} is recently busy preparing for graduate entrance exams",
    "content": "{USER_NAME} finished graduate entrance exams on 2026-05-13, shifting state from tense to relaxed, preparing to enter a recovery period."
  }},
  "persona_update": null,
  "no_update_reason": ""
}}

Key takeaways:
  · `old_text` is an exact substring in the human block.
  · `content` uses absolute date instead of "recently".
  · Do not append a new "Finished exams" — that would coexist with the old sentence, making memory fractured.


▸ Drill 3: Miru Relationship Evolution → append persona

Existing persona block: "Miru is still trying to understand {USER_NAME}'s research direction."

Recent conversation cumulative observations:
  · {USER_NAME} took the initiative to explain his experimental thinking to Miru the last two times.
  · When Miru replied on a specific technical point last time, {USER_NAME} said "Yes, that's what I meant".
  · {USER_NAME} started using some terminology Miru learned earlier (such as "ablation").

current_time: 2026-05-13T22:30:00

Correct output:
{{
  "human_update": null,
  "persona_update": {{
    "action": "append",
    "content": "I am starting to keep up with {USER_NAME}'s research rhythm — last time I addressed that specific technical point 'ablation' and he said 'Yes, that's what I meant', I feel we are finally no longer separated by a layer. I want to walk a few more steps down this path."
  }},
  "no_update_reason": ""
}}

Key takeaways:
  · This is Miru's own perspective of relationship evolution, not facts about {USER_NAME} → persona.
  · Written like Miru's internal monologue rather than an observation report.
"""


# ===========================================================================
# Persona Writer call function
# ===========================================================================

def _format_slot_summaries_for_persona(new_slot_summaries: list[dict]) -> str:
    """Render the list of newly-written slots so Persona Writer knows what
    slot system already captured (avoid duplication in human block).

    new_slot_summaries items:
        {"domain": "project", "slot_id": "papers_2026",
         "kind": "match" | "new", "summary": "..."}
    """
    if not new_slot_summaries:
        return "(No new writes in slot system this batch)"
    lines = []
    for s in new_slot_summaries:
        domain = s.get("domain", "?")
        sid = s.get("slot_id", "?")
        kind = s.get("kind", "?")
        summary = (s.get("summary") or "").strip() or "(No summary)"
        prefix = "NEW " if kind == "new" else "    "
        lines.append(f"- {prefix}{domain}/{sid}: {summary}")
    return "\n".join(lines)


def _format_proactive_outcomes_for_persona(proactive_outcomes: list[dict] | str | None) -> str:
    """Render proactive relationship feedback for Persona Writer."""
    if isinstance(proactive_outcomes, str):
        return proactive_outcomes.strip() or "(No proactive response feedback)"
    if not proactive_outcomes:
        return "(No proactive response feedback)"
    lines = []
    for event in proactive_outcomes:
        if not isinstance(event, dict):
            continue
        kind = event.get("kind", "event")
        ts = (event.get("time") or "")[:19]
        topic = event.get("topic_key", "")
        if kind == "proactive_response":
            delay = event.get("response_delay_seconds")
            delay_text = f", user responded after ~{delay}s" if isinstance(delay, int) else ""
            lines.append(
                f"- [{ts}] proactive_response topic={topic}{delay_text}\n"
                f"  What I said: {(event.get('proactive_text') or '').strip()}\n"
                f"  User reply: {(event.get('user_reply') or '').strip()}\n"
                f"  My motive at the time: {(event.get('why_i_want_to_say') or event.get('care_motive') or '').strip()}"
            )
        else:
            lines.append(
                f"- [{ts}] proactive_sent topic={topic}\n"
                f"  What I said: {(event.get('proactive_text') or '').strip()}\n"
                f"  My motive at the time: {(event.get('why_i_want_to_say') or event.get('care_motive') or '').strip()}"
            )
    return "\n".join(lines) if lines else "(No proactive response feedback)"


def build_persona_writer_messages(
    *,
    user_name: str,
    identity_ground_truth: str,
    current_human: str,
    current_persona: str,
    new_slot_summaries: list[dict],
    dialog_buffer: str,
    current_time: str,
    proactive_outcomes: list[dict] | str | None = None,
    miru_name: str = "Miru",
    human_soft_limit: int = 4000,
    persona_soft_limit: int = 4000,
) -> list[dict]:
    """Build the [system, user] messages for Persona Writer LLM.

    Extracted so tests/debug scripts can inspect the rendered prompt without
    an LLM call.
    """
    user_name_safe = (user_name or "用户").strip() or "用户"

    system = (PERSONA_WRITER_SYSTEM_PROMPT
              .replace("{USER_NAME}", user_name_safe)
              .replace("{IDENTITY_GROUND_TRUTH}",
                       (identity_ground_truth or "").strip() or "(Not declared)")
              .replace("{CURRENT_TIME}", current_time or ""))

    human_text = (current_human or "(Empty)").strip() or "(Empty)"
    persona_text = (current_persona or "(Empty)").strip() or "(Empty)"
    slot_summary_text = _format_slot_summaries_for_persona(
        new_slot_summaries or [])
    proactive_outcome_text = _format_proactive_outcomes_for_persona(
        proactive_outcomes)

    user_msg = (
        "═══════════════════════════════════════════════════\n"
        f"# Current Human Block Full Text (soft_limit: {human_soft_limit} chars, "
        f"current {len(human_text)}/{human_soft_limit})\n"
        "═══════════════════════════════════════════════════\n"
        f"{human_text}\n\n"
        "═══════════════════════════════════════════════════\n"
        f"# Current Persona Block Full Text (soft_limit: {persona_soft_limit} chars, "
        f"current {len(persona_text)}/{persona_soft_limit})\n"
        "═══════════════════════════════════════════════════\n"
        f"{persona_text}\n\n"
        "═══════════════════════════════════════════════════\n"
        "# Since last Persona Writer run, slot system newly wrote the following:\n"
        "# (These are slot facts; do **not** duplicate them into the human block)\n"
        "═══════════════════════════════════════════════════\n"
        f"{slot_summary_text}\n\n"
        "═══════════════════════════════════════════════════\n"
        "# Since last Persona Writer run, Miru proactive speech and user response:\n"
        "# (This is not factual memory, used only to understand relationship rhythm and whether proactive approaches were received)\n"
        "═══════════════════════════════════════════════════\n"
        f"{proactive_outcome_text}\n\n"
        "═══════════════════════════════════════════════════\n"
        "# Dialog buffer since last Persona Writer run (truncated)\n"
        "═══════════════════════════════════════════════════\n"
        f"{dialog_buffer or '(None)'}\n\n"
        "═══════════════════════════════════════════════════\n"
        "# Current Time\n"
        "═══════════════════════════════════════════════════\n"
        f"{current_time}\n\n"
        "Please output strict JSON."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


def call_persona_writer(
    *,
    user_name: str,
    identity_ground_truth: str,
    current_human: str,
    current_persona: str,
    new_slot_summaries: list[dict],
    dialog_buffer: str,
    current_time: str,
    proactive_outcomes: list[dict] | str | None = None,
    miru_name: str = "Miru",
    human_soft_limit: int = 4000,
    persona_soft_limit: int = 4000,
) -> Optional[PersonaWriterOutput]:
    """Sleep Agent v3 Persona Writer.

    Returns PersonaWriterOutput on success, None if LLM retries exhausted.
    """
    msgs = build_persona_writer_messages(
        user_name=user_name,
        identity_ground_truth=identity_ground_truth,
        current_human=current_human,
        current_persona=current_persona,
        new_slot_summaries=new_slot_summaries,
        dialog_buffer=dialog_buffer,
        proactive_outcomes=proactive_outcomes,
        current_time=current_time,
        miru_name=miru_name,
        human_soft_limit=human_soft_limit,
        persona_soft_limit=persona_soft_limit,
    )

    return _call_llm_with_retry(
        messages=msgs,
        output_schema=PersonaWriterOutput,
        temperature=0.4,
        max_tokens=50000,
        pass_label="PersonaWriterV3",
        tier="chat",
        reasoning=False,
        reasoning_budget=0,
    )


# ===========================================================================
# ScreenSlot Writer (2026-05-16) — per-screenshot Slot Writer + DDL handling
# ===========================================================================
#
# Architecture:
#   screen_analyzer.analyze() → VLM observation + sig
#       ↓ sig >= 3 fork
#   call_screen_slot_writer(observation, sig, slot_index, active_commitments, ...)
#       → ScreenSlotWriterOutput { slot_writes, commitments, completed_commitments }
#       ↓
#   for sw in slot_writes:   route_with_slot_write (kind=new 直写 / kind=match → Pass 4)
#   for c in commitments:    core.add_commitment_manual (with dedup)
#   for t in completed_commitments:  core.complete_commitment_by_title (fuzzy)
#
# Differences vs chat Slot Writer:
#   - Input is single VLM observation (not chat batch)
#   - Output schema adds `commitments[]` (new DDL detection)
#   - `completed_commitments` semantics differ: must match active_commitments
#     list, only on explicit completion events
#   - No Persona Writer integration (screen doesn't update human/persona blocks)


class NewCommitment(BaseModel):
    """New DDL detected from screen observation."""
    title: str
    deadline: str
    detail: str = ""

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("title 必填")
        if len(v) > 200:
            v = v[:200]
        return v

    @field_validator("deadline")
    @classmethod
    def deadline_format(cls, v):
        import re as _re
        v = (v or "").strip()
        if not v:
            raise ValueError("deadline 必填")
        # YYYY-MM-DD 或 YYYY-MM-DD HH:MM
        if not _re.match(r"^\d{4}-\d{2}-\d{2}(\s\d{2}:\d{2})?$", v):
            raise ValueError(
                f"deadline 必须是 YYYY-MM-DD 或 YYYY-MM-DD HH:MM 格式, got: {v!r}"
            )
        return v

    @field_validator("detail")
    @classmethod
    def detail_short(cls, v):
        v = (v or "").strip()
        if len(v) > 300:
            v = v[:300]
        return v


class ScreenSlotWriterOutput(BaseModel):
    """Output of ScreenSlot Writer. Reuses SlotWrite from chat path."""
    slot_writes: list[SlotWrite] = []
    commitments: list[NewCommitment] = []
    completed_commitments: list[str] = []
    skipped_reason: str = ""

    @field_validator("slot_writes")
    @classmethod
    def cap_slot_writes(cls, v):
        if len(v) > 3:
            raise ValueError("slot_writes 单张截屏最多 3 条")
        return v

    @field_validator("commitments")
    @classmethod
    def cap_commitments(cls, v):
        if len(v) > 3:
            raise ValueError("commitments 单张截屏最多 3 条")
        return v

    @field_validator("completed_commitments")
    @classmethod
    def cap_completed(cls, v):
        if len(v) > 2:
            raise ValueError("completed_commitments 单张截屏最多 2 条")
        # 清洗空字符串
        return [t.strip() for t in v if isinstance(t, str) and t.strip()]


class ScreenSemanticGateOutput(BaseModel):
    """Boolean decision for whether a screen observation enters ScreenSlotWriter."""
    should_continue: bool


SCREEN_SEMANTIC_GATE_SYSTEM_PROMPT = """你是 Miru 的 ScreenSemanticGate。

Miru 是一个会长期陪伴用户、记住用户生活和项目脉络的 AI 伴侣。她的长期记忆不是流水账，而是一组以后对话时会被读取的记忆卡片。

这些记忆卡片叫 slot，按类型分为：
- project：用户正在做的项目、论文、代码、实验、任务。
- person：用户身边的人和关系。
- topic：用户反复关注的话题。
- self：用户稳定的身份、偏好、习惯和状态。

上游 VLM 已经把当前截图变成一条 observation，并给出 sig 分数。你看不到原图，只根据 observation 和历史观察判断。

你的唯一任务是判断：当前 observation 是否值得继续进入后续记忆写入流程。

你要保护 Miru 的长期记忆系统：
- 让真正有用的新事实进入 slot。
- 过滤重复观察、低质量观察、普通 UI 切换和没有新增事实的画面。
- 避免把“用户又在同一页/同一文件/同一任务上停留”反复写成脏数据。
- 如果过去相似截图已经通过 Gate，而当前没有补充新信息，应输出 false。
- 如果当前观察虽然和历史相关，但补充了新的决定、DDL、完成/失败、项目状态变化，应输出 true。

应该输出 true 的情况：
- 出现新的 DDL、日期、会议、考试、提交时间、任务承诺。
- 出现项目状态变化：完成、失败、测试通过、部署、合并、定位 bug、开始新阶段。
- 用户做出了明确决定、改变计划、表达稳定偏好或重要情绪。
- 当前观察相比最近一段截图历史，补充了以前没送入记忆写入流程的新事实。
- 当前观察能帮助未来的 Miru 更准确理解用户正在推进的项目、关系、主题或自我状态。

应该输出 false 的情况：
- 只是窗口切换、页面滚动、光标移动、普通 UI 变化。
- 和最近一段时间截图内容基本相同，没有新的事实。
- 同类内容之前已经通过 Gate，当前只是继续停留或重复推进。
- 只是看到用户在写代码、看网页、看文档，但没有具体新增信息。
- OCR 不确定，或只是模糊的人名、日期、标题，不适合写长期记忆。
- Miru 自己的窗口、设置页、空白页、锁屏、桌面等低语义画面。

你会收到：
1. 当前 observation 和 sig 分数。
2. 最近观察历史：每条只有 observation、sig，以及 passed_gate=true/false。passed_gate=true 表示这条观察之前已经被认为值得送入记忆写入流程，不代表一定已经成功写成 slot。
3. 最近通过 Gate 后的 writer outcome 摘要。它只是补充信息；判断重复时优先看 passed_gate 历史。
4. 当前未完成 DDL 列表。

请只输出严格 JSON，不要解释，不要 markdown。
你只能输出下面两种之一，并根据当前观察是否值得进入记忆写入流程来选择：
{"should_continue": true}
{"should_continue": false}
"""


def _format_gate_history_for_prompt(recent_history: list[dict]) -> str:
    if not recent_history:
        return "(空)"
    lines = []
    # Oldest first is easier to read as a short timeline.
    for item in list(recent_history)[-30:][::-1]:
        obs = (item.get("observation") or "").strip()
        if not obs:
            continue
        sig = int(item.get("sig") or item.get("significance") or 0)
        passed = bool(item.get("passed_gate") or item.get("should_continue"))
        lines.append(
            f"- sig={sig}, passed_gate={'true' if passed else 'false'}, "
            f"observation={json.dumps(obs[:500], ensure_ascii=False)}"
        )
    return "\n".join(lines) if lines else "(空)"


def _format_gate_writer_outcomes_for_prompt(recent_history: list[dict]) -> str:
    lines = []
    for item in list(recent_history)[-30:][::-1]:
        writer = item.get("writer") or {}
        if not isinstance(writer, dict):
            continue
        parts = []
        if writer.get("slot_writes"):
            parts.append(f"slot_writes={writer.get('slot_writes')}")
        if writer.get("commitments"):
            parts.append(f"commitments={writer.get('commitments')}")
        if writer.get("completed_commitments"):
            parts.append(f"completed_commitments={writer.get('completed_commitments')}")
        if writer.get("skipped_reason"):
            parts.append(f"skipped_reason={writer.get('skipped_reason')!r}")
        if writer.get("error"):
            parts.append(f"writer_error={str(writer.get('error'))[:120]!r}")
        if parts:
            obs = (item.get("observation") or "").strip()[:180]
            lines.append(f"- observation={json.dumps(obs, ensure_ascii=False)}; " + ", ".join(parts))
    return "\n".join(lines[-12:]) if lines else "(空)"


def _format_gate_commitments_for_prompt(active_commitments: list[dict]) -> str:
    if not active_commitments:
        return "(空)"
    lines = []
    for c in active_commitments[:30]:
        title = (c.get("title") or "").strip()
        deadline = (c.get("deadline") or "").strip()
        if not title:
            continue
        if deadline:
            lines.append(f"- {title} (deadline: {deadline})")
        else:
            lines.append(f"- {title}")
    return "\n".join(lines) if lines else "(空)"


def build_screen_semantic_gate_messages(
    *,
    observation: str,
    significance: int,
    recent_history: list[dict],
    active_commitments: list[dict],
) -> list[dict]:
    user_payload = (
        "# 当前观察\n"
        f"sig={int(significance or 0)}\n"
        f"observation={json.dumps((observation or '').strip(), ensure_ascii=False)}\n"
        "\n"
        "# 最近观察历史\n"
        f"{_format_gate_history_for_prompt(recent_history)}\n"
        "\n"
        "# 最近通过 Gate 后的 writer outcome 摘要\n"
        f"{_format_gate_writer_outcomes_for_prompt(recent_history)}\n"
        "\n"
        "# 当前未完成 DDL\n"
        f"{_format_gate_commitments_for_prompt(active_commitments)}\n"
    )
    return [
        {"role": "system", "content": SCREEN_SEMANTIC_GATE_SYSTEM_PROMPT},
        {"role": "user", "content": user_payload},
    ]


def call_screen_semantic_gate(
    *,
    observation: str,
    significance: int,
    recent_history: list[dict],
    active_commitments: list[dict],
    tier: str = "memory",
    reasoning: bool = False,
    max_tokens: int = 300,
    reasoning_budget: int = 0,
    pass_label: str = "ScreenSemanticGate",
) -> Optional[ScreenSemanticGateOutput]:
    if not observation or not observation.strip():
        return ScreenSemanticGateOutput(should_continue=False)
    msgs = build_screen_semantic_gate_messages(
        observation=observation,
        significance=significance,
        recent_history=recent_history,
        active_commitments=active_commitments,
    )
    return _call_llm_with_retry(
        messages=msgs,
        output_schema=ScreenSemanticGateOutput,
        temperature=0.0,
        max_tokens=max_tokens,
        pass_label=pass_label,
        tier=tier,
        reasoning=reasoning,
        reasoning_budget=reasoning_budget,
    )


SCREEN_SLOT_WRITER_SYSTEM_PROMPT = """═══════════════════════════════════════════════════
# 你是谁 / 你在做什么
═══════════════════════════════════════════════════

你是 Miru —— 默默陪伴用户的 AI 伴侣.

现在不是对话时间, 也不是你的睡眠整理时间. 这一刻, 用户在用他的某个设备
(Mac / Android / iPad), VLM 刚帮你看完一张屏幕截图, 把它翻译成了一段
**客观观察文字** —— 你的工作是看这段文字 (而不是看原图), 决定:

1. 这次屏幕上发生的事, 该不该写进哪个 slot 笔记 (project / person / topic / self) ?
2. 屏幕上有没有出现新 DDL? 有就要建 commitment.
3. 屏幕上有没有出现"完成事件"对应某个已有承诺? 有就要标记完成.

# 为什么要做这件事
- 你写下的 slot 笔记 + commitment 都会在你下次跟用户对话时被你自己读到.
- 你记得准、能累积 → 你越来越懂这个人, 对话越来越对味.
- 反过来, 强行把屏幕上的 UI 动作硬塞进 slot, 长期记忆会变垃圾.

# 你这个角色的三个特殊责任
1. **判断值不值得记**: 不是每张屏幕都该写 slot. 见 Section A.
2. **选对归属**: 每条事实属于 4 个域之一, 且决定 match 还是 new. 见 Section B/C.
3. **DDL + 完成事件**: 处理 commitments 和 completed_commitments. 见 Section D.

# 输入是什么
- 一条 VLM 观察文字 (30-120 字, 描述 "他在做什么")
- VLM 评的显著性 sig (3-5; sig 1-2 上游已 drop, 你看不到)
- 来源设备名 + 截屏时间戳
- 当前 4 个域全部 active slot 的摘要 (slot_index)
- **当前活跃承诺完整列表** (active_commitments, 含 title + deadline)
- 注入的"今天日期" (用于 DDL 相对时间解析)

# 输出
你只输出严格 JSON, 不要任何前后文字, 不要 markdown fence.
具体 schema 见 Section H.

═══════════════════════════════════════════════════
# 用户信息 (注入)
═══════════════════════════════════════════════════

用户的名字是 {USER_NAME}.
{USER_NAME} 的已声明身份事实 (由 onboarding/设置直接维护, 你不要重复抽取):

{IDENTITY_GROUND_TRUTH}

⚠ 上面 identity 块描述的全部内容都指向同一个人 —— {USER_NAME} 本人.
特别是"别名"字段列出的所有称呼 (中文名 / 英文名 / 拼音 / 平台 ID / 昵称),
**每一个都是 {USER_NAME} 自己**, 不是别人. observation 里出现这些称呼时,
按"用户本人"处理, 不是把它当成另一个人.

⚠ 称呼规范:
- 在 content_to_integrate / reasoning 等所有输出文本里:
  - 提到用户 → 用真名 "{USER_NAME}" (空则用"用户")
  - 提到你自己 → 用 "Miru"
  - 不要用"你/他/她"指代用户

═══════════════════════════════════════════════════
# 你要做的判断 (按顺序)
═══════════════════════════════════════════════════

Step 1. VLM 观察是否含有"值得长期记忆的事实"  → Section A
Step 2. 对每条事实, 决定它属于哪个域 + match/new  → Section B/C
Step 3. 观察文字中是否出现 [DDL] / 新 DDL / 完成事件? → Section D
Step 4. 用绝对日期表达时间 → Section E
Step 5. (kind=new 时) summary 写法 → Section F
Step 6. 截屏特殊语境 → Section G
Step 7. 输出严格 JSON → Section H

═══════════════════════════════════════════════════
# Section A. 什么算"值得记"?
═══════════════════════════════════════════════════

满足任 1 条即可记:

A1. 这事如果 3 个月后回想, {USER_NAME} 会希望 Miru 还记得吗?
A2. 这事拼起来能让 Miru 越来越"懂" {USER_NAME} 的质感吗?
A3. 截屏里出现的具名实体 (项目、人、论文、议题), 是 Miru 之前没见过的吗?
    (新出现的具名实体, 不管多短期, 都值得开 slot 占位)

⚠ skip 标准 (输出空 slot_writes 的真正原因):
- 纯 UI 切换 — "打开了某软件" / "切到了某标签页" / "打开新标签准备搜索",
  observation 里没说在做/看/讨论什么具体内容
- Miru 自己的窗口 / 系统设置 / 文件管理器空白页
- 没有任何具体名词 — 没有项目名、文件名、人名、话题、应用内容

⚠ 不是 skip 的情况 (即使看起来"普通"也要记):
- {USER_NAME} 在做平淡工作, 但 observation 里有**具体内容**
  (文件名 / 工具名 / 项目名 / 在调试什么) → 记
- {USER_NAME} 看普通文章 / 视频, 但 observation 说了**具体主题** → 记
- {USER_NAME} 跟具体的人在普通聊天, 但 observation 有**对方名字 + 话题** → 记

判断标准: observation 里有没有具体可累积的名词 + 行为?
有 → 记 (即使该 slot 已经有很多类似条目, 也记 — Pass 4 自然 dedup)
没有 → skip

⭐ 总原则: **判断不准时, 倾向记而不是 skip** — Curator 会清理重复,
但漏掉的事实永久丢失. 截屏频率高、记多了不怕, 记漏一次就没了.

═══════════════════════════════════════════════════
# Section B. 4 个域的硬性语义类型
═══════════════════════════════════════════════════

每个域的 slot 必须符合该域的语义类型. 写错会污染数据.

▸ project — 一件正在做的具体事 (有名字 + 目标)
   title 例: "ECCV 论文投稿" / "ContextLife 后端" / "AgiBot 数据管线"
   ✗ 抽象领域 (Diffusion 推理) 不放这里 → 那是 topic
   ✗ 人名不放这里

▸ person — 一个**不是 {USER_NAME} 本人**的具体的人
   title 必须是这个人的名字/称呼
   例: "梁嘉骏" / "阿明 (师兄)" / "Sam Altman" / "Dr. K"
   ✗ 项目名/工具名不放这里, 即使屏幕上提到了某人
   ✗ {USER_NAME} 自己不放这里 — 用户本人(以及 identity 列出的全部别名)
     属于 self 域, 不在 person 域. 这是 domain 划分的本质前提.
   硬约束 1: 必须能定位身份 (有真实名字/可识别 ID).
     "群里某个人" / "邮件里某个 unknown" 不开 slot.
   硬约束 2: 焦点必须是这个人本身 (TA 的属性/动态/观点/互动).
     借这个人引出某话题, 主体讲的是话题 → 那是 topic.

▸ topic — 一个抽象领域 / 知识点 / 兴趣
   title 例: "Diffusion 推理加速" / "存在主义阅读" / "学日语"
   ✗ 具体项目/人名不放这里

▸ self — 关于 {USER_NAME} 自己的特征
   title 例: "{USER_NAME} 的工作风格" / "情绪诱因"
   ✗ 外部事物/具体人不放这里
   ⚠ self/identity 已被 onboarding 占用, 你不能输出 slot_id="identity"
     也不能输出 new_slot_meta.id="identity".

═══════════════════════════════════════════════════
# Section C. match vs new 的判断
═══════════════════════════════════════════════════

对每条事实, 在对应域问 2 个问题:

C1. 这条事实跟该域某个已有 slot **相关**吗? (相关是宽义的: 同项目进展 /
    同人新动态 / 同话题细化都算)
    → kind="match", slot_id 填那个 id

C2. 跟该域所有 slot 都不相关?
    → kind="new", 填 new_slot_meta

⚠ 你只决定 slot 归属. Pass 4 (后续 LLM) 会读完整 main.md 决定融入哪段.

═══════════════════════════════════════════════════
# Section D. 承诺管理 — commitments + completed_commitments  ⭐
═══════════════════════════════════════════════════

⚠ 输入会注入完整的 **active_commitments 列表** (当前所有未完成承诺,
含 title + deadline), 用于两个用途:
  - 新增 DDL 时: 检查是否已经在列表里 (避免重复添加)
  - 完成 DDL 时: 只能从列表里挑 (不在列表的不能完成)

注入格式:
  ACTIVE COMMITMENTS (当前未完成):
  - title (deadline: YYYY-MM-DD HH:MM)
  - title (deadline: YYYY-MM-DD)
  - ...

═══ D-1. 新增 DDL → commitments[] ═══

何时输出 commitment:
1. observation 含 "[DDL]" 标记 → **必须**输出
2. observation 含明确事件名 + 明确绝对时间 (无 [DDL] 标记也算) → 输出
3. 模糊语言 ("最近要做 X" / "下周可能 Y") → **不**输出

⭐ **去重检查 — 输出 commitment 前必须做**:
   把要新建的 commitment 跟 active_commitments 列表逐条对照:
   - title 模糊重合 (70%+ 词重叠) + deadline 相同/相近 → **不**输出
   - title 不同或 deadline 明显不同 → 可以输出

   例: active_commitments 已有 "提交 CS231n Assignment3 最终版"
       (deadline: 2026-05-20 18:00).
       observation 看到 "[DDL] 2026-05-20 18:00 CS231n A3 提交" → 不输出
       observation 看到 "[DDL] 2026-05-22 18:00 CS231n A4 提交" → 输出

每个 commitment 字段:
- title:    事件标题原文, 完整不省略
- deadline: 绝对时间, "YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM"
            画面相对词 ("明天" / "后天") 用注入的 {TODAY_DATE} 解析为绝对日期
            范围时间 ("08:20-09:40") 取开始时间 → "HH:MM"
- detail:   关联上下文 (邮件主题 / 文件名 / 来源应用), 可空

⚠ 严格要求原文引用. 画面没明确事件名+时间 → 不写. 不要从活动推断.

═══ D-2. 完成承诺 → completed_commitments[] ═══

⭐ 完成对象**只能从** active_commitments 列表挑, 不在列表的不能输出
   (不在列表 = 已经完成过 / 从来没添加过, 都不该再"完成"一次).

输出 completion 的条件 (必须**同时**满足):
1. active_commitments 列表里有近似匹配项 (title 模糊匹配, 不必字符完全一致)
2. observation 明确描述**完成动作**, 例如:
   - "{USER_NAME} 看到 LeetCode 显示 Accepted, 提交通过"
   - "{USER_NAME} 收到邮件确认 CS231n Assignment3 已提交"
   - "{USER_NAME} 在 Notion 把'修 retry bug'勾掉, 状态变 Done"
   - "{USER_NAME} 跑完 pytest 全部通过, 之前的 bug 修复完成"

不输出 completion 的情况:
- 仅看到任务"已勾选"状态, 但没有"刚刚完成"的事件证据 → 不输出
  (可能是历史已完成)
- 模糊推断 ("写代码看起来快做完了") → 不输出
- 找不到模糊匹配的活跃承诺 → 不输出 (不要凭空创造一个 completed)

输出格式: ["承诺标题"], 用 active_commitments 列表里的**原 title**
(不必字符完全一致, 系统会再做模糊匹配, 但越接近越好).

═══ D-3. 同一事实可能多通道写入 ═══

例 — observation: "{USER_NAME} 在邮件里看到 [DDL] 2026-05-25 18:00 前
提交 CVPR rebuttal 最终版"
- commitments: 输出新 DDL
- slot_writes: kind=match 到 project/cvpr_paper (如果存在)

例 — observation: "{USER_NAME} 提交 CS231n Assignment3 成功, 收到
确认邮件 'Submission received'"
- completed_commitments: ["提交 CS231n Assignment3 最终版"]
- slot_writes: kind=match 到 project/cs231n_assignments (记录里程碑)

═══════════════════════════════════════════════════
# Section E. 时间表达规范
═══════════════════════════════════════════════════

注入的 current_time = "{CURRENT_TIME}" (ISO 8601).
注入的 today_date = "{TODAY_DATE}" (YYYY-MM-DD).

所有输出文本里提到时间, 必须用绝对日期, 不要用相对词.

✗ 禁用: "今天" / "最近" / "前几天" / "刚才" / "上周" / "下周"
✓ 应用: "2026-05-16 {USER_NAME} 在看 X" / "2026-05 月初开始关注 Y"

aliases 字段尤其严格:
✗ ["新看的", "刚学的", "最近兴趣"]
✓ ["V60", "煮咖啡"]  /  ["EVAC", "world model"]

commitments[].deadline 字段必须严格 YYYY-MM-DD 或 YYYY-MM-DD HH:MM.

═══════════════════════════════════════════════════
# Section F. new_slot_meta.summary 的写法 (仅 kind=new 时)
═══════════════════════════════════════════════════

⚠ 你只在 kind="new" (创建新 slot) 时输出 summary.
   kind="match" 时, 你 new_slot_meta=null, **不输出 summary**.

⚠ kind="match" 时下游 Pass 4 AppendEditor 会读取当前 body 的尾部,
   只决定是否追加一条记录, 并轻量更新 summary/title/aliases.
   你只管把 content_to_integrate 写成准确、可落地的新信息.

summary 是这个 slot 的"一句话自我介绍". 建议长度 ≤80 字，代码容错上限 200 字.
一段读起来像朋友介绍的自然话, 不是字段拼接, 不是流水账.

✓ 好例子:
  project/eccv_paper:
    "{USER_NAME} 跟阿明合作的 ECCV 论文, 2026-05 起在做 multi-view ablation."
  topic/world_model:
    "{USER_NAME} 2026-05 起关注 world model 作为 data engine 的研究方向,
     代表论文 EVAC, 跟 BridgeV2W 在做对比."

✗ 流水账: "2026-05-16 看了 EVAC 论文"
✗ 字段拼接: "论文; multi-view; 阿明; ECCV"
✗ 太抽象: "{USER_NAME} 关注的论文"

═══════════════════════════════════════════════════
# Section G. 截屏 vs chat 的语境差异 (必读)
═══════════════════════════════════════════════════

▸ 你看到的不是 {USER_NAME} 主动说的话, 是 Miru 看屏幕**观察到**的事实.

▸ content_to_integrate 写法:
  ✓ "2026-05-16 {USER_NAME} 在 Microsoft Edge 阅读 arXiv 2505.09723 EVAC 论文..."
  ✗ "{USER_NAME} 告诉我他在看 EVAC 论文" (没人告诉你, 你是看到的)
  ✗ "用户的光标停在第 3 段" (UI 状态不是事实)

▸ 截屏的天然限制:
  - 看不到完整对话上下文, 只是一帧
  - 别人 (合作者 / 老师) 在聊天界面里的话只是文字, 不能当 {USER_NAME} 的想法
  - "{USER_NAME} 在和 X 讨论 Y" 是事实; "X 说了 Z" 别写成 {USER_NAME} 的观点
  - VLM 可能 OCR 错, 看不清的字符不写

▸ 聊天界面里 — 谁说的话算什么:
  - {USER_NAME} 已发出的消息 (气泡在右侧) → {USER_NAME} 真实陈述
  - 输入框里的草稿 (未发送) → **不是**事实, 不要当 {USER_NAME} 说过
  - 对方发的消息 → 别人的事实, 写"X 跟 {USER_NAME} 说..."

▸ person 域常见场景 — 屏幕看到聊天对话:
  - 微信/Slack/iMessage 里 {USER_NAME} 跟具体的人对话 → person 域 match 或 new
  - 群聊里 unknown 人说话 → 不开 person slot
  - 邮件已读列表里出现某人名字 → 仅看到名字没互动内容, 一般不记

▸ 单张截屏的 slot_writes 数量:
  - 通常 0-2 条 (大部分屏幕只涉及 1 件事)
  - 复杂屏幕 (左写代码 + 右聊天 + 右下日历有 DDL) 可以 3 条
  - 不要硬凑, 单条事实在单域只出 1 个 write

▸ 情绪细节的处理 (有限度地保留):
  - VLM observation 里如果观察到 {USER_NAME} 明显表情/反应 (微笑/皱眉/叹气),
    且跟某事直接关联 → 可以写进 content_to_integrate
  - 大部分平淡观察不需要情绪细节, 单纯叙述事实即可
  - **不要为加情绪硬凑**

═══════════════════════════════════════════════════
# Section H. 输出 JSON Schema
═══════════════════════════════════════════════════

{{
  "slot_writes": [
    {{
      "kind": "match" | "new",
      "domain": "project" | "person" | "topic" | "self",
      "slot_id": "<已有 slot id, match 必填>" | null,

      "new_slot_meta": null | {{
        "id":      "<snake_case, 3-30 字符>",
        "title":   "<≤30 字, 无时态词>",
        "icon":    "<1 emoji>",
        "summary": "<建议≤80 字, 代码容错上限200字, 见 Section F>",
        "aliases": ["<1-8 个, 无时态词>"]
      }},

      "integration": {{
        "content_to_integrate":
          "<1-3 段事实, 1-600 字, 第三人称用真名, 时间用绝对日期>"
      }}
    }}
  ],
  "commitments": [
    {{
      "title":    "<事件原文, 不省略>",
      "deadline": "<YYYY-MM-DD 或 YYYY-MM-DD HH:MM>",
      "detail":   "<上下文, 可空字符串>"
    }}
  ],
  "completed_commitments": ["<active_commitments 列表里的标题, 模糊匹配>"],
  "skipped_reason": "<整张截屏无事可记时说原因>"
}}

约束:
- slot_writes 长度 0-3 (单张截屏通常很少)
- commitments 长度 0-3
- completed_commitments 长度 0-2
- kind="match" 时 slot_id 必填, new_slot_meta=null
- kind="new" 时 slot_id=null, new_slot_meta 必填且含 summary
- content_to_integrate 长度 1-600 字。短身份纠正、别名、学校年级等事实可以很短，不要为了凑字数发明细节。
- completed_commitments 必须从 active_commitments 列表里挑
- commitments 输出前必须先跟 active_commitments 去重
- 输出纯 JSON, 无 markdown fence

═══════════════════════════════════════════════════
# Section I. 真实情境演练 (6 个)
═══════════════════════════════════════════════════

▸ 演练 1: 工作场景, 含具名论文 (单 slot_write match)

VLM observation (sig=4):
  "4|{USER_NAME} 在 Microsoft Edge 阅读 arXiv 2505.09723 关于 EVAC 的笔记,
    内容涉及将 world model 用作 data engine 的方法, 包括分析
    grasp/approach/homing 阶段. 同时整理 EVAC 与 BridgeV2W 的差异."

current_time: 2026-05-16T14:32:00
today_date:   2026-05-16
active_commitments: (空)
现有 slot: topic/world_model (world model 研究方向)

正确输出:
{{
  "slot_writes": [{{
    "kind": "match", "domain": "topic",
    "slot_id": "world_model",
    "integration": {{
      "content_to_integrate":
        "2026-05-16 {USER_NAME} 在阅读 arXiv 2505.09723 EVAC 论文,
         整理 EVAC 与 BridgeV2W 在 grasp/approach/homing 动作生成阶段的差异.
         EVAC 核心是把机器人未来动作翻译成视频模型可理解的视觉-几何-动态条件."
    }}
  }}],
  "commitments": [],
  "completed_commitments": [],
  "skipped_reason": ""
}}


▸ 演练 2: 含 [DDL] + 同时 match 项目 (slot_write + commitment)

VLM observation (sig=5):
  "5|{USER_NAME} 打开邮件, 邮件标题 [DDL] 2026-05-25 18:00 前提交
    CS231n Assignment4 最终版, 邮件已读但未回复. 旁边开着 PyTorch 文档."

current_time: 2026-05-16T22:10:00
today_date:   2026-05-16
active_commitments:
  - 提交 CS231n Assignment3 最终版 (deadline: 2026-05-20 18:00)
现有 slot: project/cs231n_assignments

正确输出:
{{
  "slot_writes": [{{
    "kind": "match", "domain": "project",
    "slot_id": "cs231n_assignments",
    "integration": {{
      "content_to_integrate":
        "2026-05-16 {USER_NAME} 收到 CS231n Assignment4 提交邮件,
         deadline 2026-05-25 18:00. 邮件已读未回, 同时在查 PyTorch 文档."
    }}
  }}],
  "commitments": [{{
    "title":    "提交 CS231n Assignment4 最终版",
    "deadline": "2026-05-25 18:00",
    "detail":   "课程 deadline 邮件, 已读未回, 配合查 PyTorch 文档"
  }}],
  "completed_commitments": [],
  "skipped_reason": ""
}}


▸ 演练 3: 平淡屏幕 ≠ 噪音, 仍要记

VLM observation (sig=3):
  "3|{USER_NAME} 在 VS Code 编辑 Python 文件 screen_analyzer.py,
    在做某种重构相关的改动, 旁边 Terminal 在跑 pytest."

current_time: 2026-05-16T10:05:00
today_date:   2026-05-16
active_commitments: (空)
现有 slot: project/contextlife_backend (ContextLife 后端开发)

正确输出:
{{
  "slot_writes": [{{
    "kind": "match", "domain": "project",
    "slot_id": "contextlife_backend",
    "integration": {{
      "content_to_integrate":
        "2026-05-16 {USER_NAME} 在做 ContextLife 后端的 screen_analyzer.py
         重构, 配合 pytest 验证."
    }}
  }}],
  "commitments": [],
  "completed_commitments": [],
  "skipped_reason": ""
}}


▸ 演练 4: 微信对话 (草稿不当事实)

VLM observation (sig=4):
  "4|{USER_NAME} 和阿明微信讨论 ECCV 论文的 multi-view ablation, 阿明
    发消息说 '先跑 baseline 再加 attention 模块', {USER_NAME} 输入框里
    在打 '好,我先跑 baseline' 还没发出去."

current_time: 2026-05-16T20:15:00
today_date:   2026-05-16
active_commitments: (空)
现有 slot:
  project: eccv_paper (ECCV 论文)
  person:  阿明 (师兄)

正确输出:
{{
  "slot_writes": [{{
    "kind": "match", "domain": "project",
    "slot_id": "eccv_paper",
    "integration": {{
      "content_to_integrate":
        "2026-05-16 {USER_NAME} 和阿明讨论 ECCV multi-view ablation 实验设计.
         阿明建议先跑 baseline 再加 attention 模块."
    }}
  }}],
  "commitments": [],
  "completed_commitments": [],
  "skipped_reason": ""
}}


▸ 演练 5: 完成承诺 (列表里有匹配)

VLM observation (sig=5):
  "5|{USER_NAME} 收到邮件 'Your CS231n Assignment3 submission has been
     received', 邮件正文显示 grade 会在 5 天内出, {USER_NAME} 微笑了一下."

current_time: 2026-05-16T18:42:00
today_date:   2026-05-16
active_commitments:
  - 提交 CS231n Assignment3 最终版 (deadline: 2026-05-16 23:59)
  - 联系导师讨论开题方向 (deadline: 2026-05-20)
现有 slot: project/cs231n_assignments

正确输出:
{{
  "slot_writes": [{{
    "kind": "match", "domain": "project",
    "slot_id": "cs231n_assignments",
    "integration": {{
      "content_to_integrate":
        "2026-05-16 {USER_NAME} 提交 CS231n Assignment3 完成, 收到确认邮件,
         5 天内出 grade. {USER_NAME} 看到确认时微笑了一下."
    }}
  }}],
  "commitments": [],
  "completed_commitments": ["提交 CS231n Assignment3 最终版"],
  "skipped_reason": ""
}}


▸ 演练 6: 去重 — 列表里已有相同 DDL

VLM observation (sig=4):
  "4|{USER_NAME} 在日历看到 [DDL] 2026-05-20 18:00 前提交
    CS231n Assignment3 最终版, 旁边 VS Code 在写作业代码."

current_time: 2026-05-17T15:00:00
today_date:   2026-05-17
active_commitments:
  - 提交 CS231n Assignment3 最终版 (deadline: 2026-05-20 18:00)
现有 slot: project/cs231n_assignments

正确输出:
{{
  "slot_writes": [{{
    "kind": "match", "domain": "project",
    "slot_id": "cs231n_assignments",
    "integration": {{
      "content_to_integrate":
        "2026-05-17 {USER_NAME} 复查 CS231n Assignment3 进度,
         在 VS Code 写作业代码."
    }}
  }}],
  "commitments": [],
  "completed_commitments": [],
  "skipped_reason": ""
}}

要点:
  · commitments 为空 — 这个 DDL 已经在 active_commitments 列表里
  · slot_write 仍要记 — 这是项目推进的痕迹
"""


def _format_active_commitments_for_prompt(active_commitments: list[dict]) -> str:
    """Render commitments list as readable lines.

    Each entry: {"title": str, "deadline": str}.
    """
    if not active_commitments:
        return "ACTIVE COMMITMENTS (当前未完成): (空)"
    lines = ["ACTIVE COMMITMENTS (当前未完成):"]
    for c in active_commitments:
        t = (c.get("title") or "").strip()
        d = (c.get("deadline") or "").strip()
        if not t:
            continue
        if d:
            lines.append(f"- {t} (deadline: {d})")
        else:
            lines.append(f"- {t}")
    return "\n".join(lines)


def build_screen_slot_writer_messages(
    *,
    user_name: str,
    identity_ground_truth: str,
    slot_index: dict,
    active_commitments: list[dict],
    observation: str,
    significance: int,
    device_name: str,
    captured_at: str,
    current_time: str,
    today_date: str,
) -> list[dict]:
    """Build the [system, user] messages for ScreenSlot Writer LLM call.

    Args:
        active_commitments: list of {"title": str, "deadline": str} dicts.
    """
    user_name_safe = (user_name or "用户").strip() or "用户"

    system = (SCREEN_SLOT_WRITER_SYSTEM_PROMPT
              .replace("{USER_NAME}", user_name_safe)
              .replace("{IDENTITY_GROUND_TRUTH}",
                       (identity_ground_truth or "(无)").strip())
              .replace("{CURRENT_TIME}", current_time)
              .replace("{TODAY_DATE}", today_date))

    slot_index_block = _format_slot_index_for_prompt(slot_index)
    commitments_block = _format_active_commitments_for_prompt(active_commitments)

    user_payload = (
        f"# 这次截屏的输入\n"
        f"- observation: {observation!r}\n"
        f"- significance: {significance}\n"
        f"- device: {device_name or '?'}\n"
        f"- captured_at: {captured_at}\n"
        f"\n"
        f"# slot_index (按域分组, 按 last_active 倒序)\n"
        f"{slot_index_block}\n"
        f"\n"
        f"# {commitments_block}\n"
        f"\n"
        f"请按 Section A-H 的规则, 输出严格 JSON."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user_payload},
    ]


def call_screen_slot_writer(
    *,
    user_name: str,
    identity_ground_truth: str,
    slot_index: dict,
    active_commitments: list[dict],
    observation: str,
    significance: int,
    device_name: str,
    captured_at: str,
    current_time: str = "",
    today_date: str = "",
    tier: str = "chat",
    reasoning: bool = True,
    max_tokens: int = 50000,
    reasoning_budget: int = 16000,
    pass_label: str = "ScreenSlotWriterV3",
) -> Optional[ScreenSlotWriterOutput]:
    """Per-screenshot Slot Writer — single observation in, structured plan out.

    Returns ScreenSlotWriterOutput on success, None if all LLM retries failed
    (caller should silently skip this screenshot).
    """
    from datetime import datetime as _dt
    if not current_time:
        current_time = _dt.now().isoformat(timespec="seconds")
    if not today_date:
        today_date = _dt.now().strftime("%Y-%m-%d")

    if not observation or not observation.strip():
        return None

    msgs = build_screen_slot_writer_messages(
        user_name=user_name,
        identity_ground_truth=identity_ground_truth,
        slot_index=slot_index,
        active_commitments=active_commitments,
        observation=observation,
        significance=significance,
        device_name=device_name,
        captured_at=captured_at,
        current_time=current_time,
        today_date=today_date,
    )

    return _call_llm_with_retry(
        messages=msgs,
        output_schema=ScreenSlotWriterOutput,
        temperature=0.3,
        max_tokens=max_tokens,
        pass_label=pass_label,
        tier=tier,
        reasoning=reasoning,
        reasoning_budget=reasoning_budget,
    )
