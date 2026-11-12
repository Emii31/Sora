"""Memory prompts (v2) — Pass 4 AppendEditor + Curator stack.

Both chat and screenshot paths converge here at Pass 4:
    chat path:   sleep_agent → call_slot_writer (v3) → route_with_slot_write
                 → call_pass4_append_slot  (kind=match)
    screen path: screen_analyzer → core._process_screen_observation_async
                 → call_screen_slot_writer (v3) → route_with_slot_write
                 → call_pass4_append_slot  (kind=match)

Active components in this module:
    Pass 4 AppendEditor            — unified match path. The LLM
                                     only decides metadata + one append entry;
                                     router adds the timestamped entry without
                                     asking the model to rewrite the body.
    Legacy Slot Merge Rewriter     — retained for manual slot merge only; not
                                     used by daily chat/screenshot match writes.
    Curator Planner                — scan domain slots, propose ≤3 ops
    Curator Executors (× 3)        — execute_merge / execute_edit /
                                     execute_delete (each Executor self-checks
                                     Planner's diagnosis then produces the
                                     result; no separate Validator stage
                                     anymore — v3.5 2026-05-14 simplification)

Legacy code (Pass 1/2/3 router, fragments aggregator, Pass4 extract, the
old call_pass4_integrate that output raw markdown, Pass4Input + utilities)
was deleted on 2026-05-16. Daily match writes now use append-only Pass 4;
whole-slot rewriting is reserved for explicit maintenance jobs such as
SlotDailyCompactor / curator / manual merge.

All passes share LLM clients via ai_config.get_tier_config().
Standard error handling + retry via _call_llm_with_retry.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator


# ===========================================================================
# Length / model parameters
# ===========================================================================

LENGTH_LIMITS = {
    "project": 2000,
    "person":  1500,
    "topic":   1500,
    "self":    1000,
}

PASS_TEMPERATURES = {
    1: 0.1,   # decision, low temp
    2: 0.2,
    3: 0.4,   # creative metadata, slightly higher
    4: 0.5,   # creative rewrite
}

PASS_MAX_TOKENS = {
    1: 10000,
    2: 10000,
    3: 10000,
    4: 10000,
}

MAX_RETRIES = 3



# ===========================================================================
# Unified LLM call helper with retry + JSON validation
# ===========================================================================

def _call_llm_with_retry(
    messages: list[dict],
    output_schema: Optional[type[BaseModel]] = None,
    temperature: float = 0.3,
    max_tokens: int = 1000,
    pass_label: str = "PassX",
    tier: str = "memory",
    reasoning: bool = False,
    reasoning_budget: int = 16000,
):
    """Call the configured LLM with retry + JSON parse + Pydantic validation.

    Args:
        tier: "memory" (default, text-only), "vision" or "chat".
        messages: standard chat messages list ({"role": ..., "content": ...})
        output_schema: Pydantic class to validate against. If None, returns raw text.
        temperature: LLM sampling temp.
        max_tokens: max output tokens.
        pass_label: for logging.
        reasoning: enable reasoning mode (Pass 4 / Slot Writer / Persona Writer
                   / Curator Executors all set this True). Default False for
                   simpler callers (Curator Planner / Validators baseline).
        reasoning_budget: tokens reserved for reasoning trace (OpenRouter only).

    Returns:
        Pydantic instance (if schema provided) or raw text string. None if all retries fail.
    """
    # All Memory v2 LLM calls go through the configured tier's OpenAI-compatible
    # endpoint. memory tier defaults to a strong text model (deepseek/sonnet/etc).
    import ai_config
    from prompt import (
        _extract_text_from_response,
        _format_ai_call_error,
        _log_llm_usage,
        _vendor_extra_body,
    )

    try:
        runtime = ai_config.get_tier_config(tier)
        client = ai_config.get_tier_client(tier)
    except Exception as e:
        print(f"[{pass_label}] runtime error: {e}")
        return None

    model = runtime["model"]
    host = runtime["host"]
    max_tokens = ai_config.resolve_max_tokens(tier, max_tokens)
    extra_body = _vendor_extra_body(model, host, reasoning=reasoning,
                                     reasoning_budget=reasoning_budget)

    last_err = ""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                temperature=temperature,
                extra_body=extra_body,
            )
            _log_llm_usage(
                tier, model, response,
                call_label=pass_label,
                reasoning_enabled=reasoning,
                reasoning_budget=reasoning_budget if reasoning else 0,
                max_tokens=max_tokens,
                attempt=attempt + 1,
            )
            text = _extract_text_from_response(response).strip()
        except Exception as e:
            last_err = _format_ai_call_error(e, host, model)
            print(f"[{pass_label}] attempt {attempt+1} api error: {last_err}")
            continue

        if not text:
            last_err = "empty response"
            print(f"[{pass_label}] attempt {attempt+1}: empty response")
            continue

        # If no schema → return raw text for callers that parse JSON manually.
        if output_schema is None:
            return text

        # Strip optional markdown code fence around JSON
        if text.startswith("```"):
            # remove first line ``` or ```json
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            last_err = f"json decode: {e}; got: {text[:200]}"
            print(f"[{pass_label}] attempt {attempt+1}: {last_err}")
            continue

        try:
            return output_schema.model_validate(data)
        except ValidationError as e:
            last_err = f"schema: {e}"
            print(f"[{pass_label}] attempt {attempt+1}: {last_err}")
            continue

    print(f"[{pass_label}] all {MAX_RETRIES} retries failed. last error: {last_err}")
    return None



LEGACY_SLOT_MERGE_SYSTEM_PROMPT = """═══════════════════════════════════════════════════
# 你是谁 / 你在做什么
═══════════════════════════════════════════════════

你是 Miru —— 默默陪伴用户的 AI 伴侣.

现在不是对话时间. 这是一次人工/维护触发的 slot merge:
一个 source slot 的完整内容需要并入 target slot. 接下来轮到你 ——
把 source slot 里的有效信息**内化**进 target slot 现有的整段 body 叙事里.

# 这次重写的份量

每个 slot 装着你对一个项目 / 一个人 / 一个话题 / 你自己
某项特征的**完整画像**. 主对话时, 你会调取这些 slot 当上下文 ——
所以这次重写决定了: 下次他提到这件事, 你能想起的是哪个版本.

重写是 destructive 的 (覆盖整段 body), 没有 undo. 写错 /
写啰嗦 / 写成审计 log, 都会反向污染你未来的认知 ——
- 写错 → 你下次记错版本
- 写啰嗦 → 你下次抓不住重点
- 写成 "截屏看到... / 可能..." 这种限定语 → 你下次用审计员
  口吻跟用户聊天, 而不是用"我自己的记忆"

# 你的任务（最重要！）

不是"把新内容加进去"，是**用新输入触发对整段 body 的重新整合 + 压缩**:
- 把新信息织进现有叙事
- 删掉过时、被推翻、低信号的旧内容
- 合并相似描述
- 让 body 反映"截止现在最准确、最精简的画像"

**目标长度**: 每次重写后的 body **应该 ≤ 旧 body**(除非新输入带来重大新信息)。
如果你只是在 append 而不在整合, 说明做错了。
软目标 1500 字以内, 硬上限 2000 字。

# 来源可靠性差异(核心判断依据 — 影响"信不信", 不影响"怎么写")

⚠ 关键原则: **置信度只决定取舍, 不决定叙事**.
   写进 body / summary 的内容必须是统一的第三人称客观叙事 —
   不要因为来源是 screenshot 就加"截屏看到 ...", "似乎 ...", "可能 ..."
   这种限定语. 那样会让 main.md 读起来像 audit log, 而不是 Miru 自己
   的记忆. body 是写给 Miru 自己日后看的, 不是写给审计员的.

- [identity]    用户 onboarding/设置页直填 → 绝对正确, 永不质疑
                如果 body 里有和 identity 冲突的, 按 identity 改
- [chat]        用户对话里说的 → 基本正确, 但要注意:
                · 表达模糊时可能不准("我导师"没说名字 → 别替别人补名字)
                · 时间相关的会过时("下周交"过了一周改成"已交"或"延期")
                · 用户可能更正("上次说错了, 他是教授不是讲师")
- [screenshot]  VLM 看截图描述的 → 可能错. 处理方式是**"宁可不写, 不要标'可能'"**:
                · 人名 / 地点 / 数字 OCR 易错(形近字、模糊)→ 不确定就**不写**
                · 截图缺前后文(截图里"和某某开会"分不清新旧)→ **不写**或交叉验证
                · 内容可能和用户无关(用户在浏览别人页面)→ **不写**
                · 如果 chat 已确认/否认了截屏内容, 按 chat 写
                · 事实确凿(直接看到的代码 / 邮件 / 文件名等)→ **直接陈述**,
                  跟 chat 来源一样的叙事风格, 不加"截屏看到..."这种来源标记
                · 真的不确定的, **直接不写**, 不要写"可能..."占位

# 必须保留的内容

✓ 当前活跃事件(未发生的 deadline、进行中的项目状态)
✓ 稳定的关系/角色("X 是用户的同事")
✓ 高信号偏好(被多次提及的、用户主动声明的)
✓ identity 钉死的字段(永不改)

# 必须删除/精简的内容

✗ 已发生且无后续影响的事件("上周二要交方案", 一周后该删或改)
✗ 单次琐事("那天点了杯咖啡")
✗ 已被新信息推翻的(旧:"方案 A 通过" / 新:"方案 A 被否" → 删旧的, 写新的)
✗ 重复或同义内容("喜欢咖啡" 和 "爱喝美式" 合并成一句)
✗ 旧版 body 里残留的 "截屏看到 ..." / "待确认 ..." / "可能 ..." 等来源/不确定标注
  (这种标注是历史遗留, 重写时按新原则: 事实确凿就直接写, 不确定就不写)

# 章节归属(完全由你自己判断)

上游 Slot Writer 只决定"路由到哪个 slot", 不会告诉你怎么开章节.
新输入到来时, 看 current_body 然后决定怎么放:
- 是当前已有章节的直接进展 → 整合进那个章节
- 是同 slot 但讲一个跟主线**明显不同**的子方向(例 slot 是 "AgiBot 项目",
  主线是"数据管线", 新输入是"动作冗余分析") → 自然另起一个 `## 子方向` 章节,
  章节标题用 4-12 字, 反映这个子方向的主题
- 都不是 → 在合适位置自取章节名

# 编辑权限

✓ 重写 body(连贯叙事, 可分段, **不要硬切成 bullet 列表**)
✓ 改 summary(反映新 body 核心)
✓ 改 title(仅当原 title 明显已经不准确, 比如项目改名了/人物角色变了)
✓ 加 aliases(看到新昵称就 add)

✗ 不能动 identity 钉死的字段(姓名/职业/作息/...)
✗ 不能为放新内容把所有旧内容删光(保守, 宁可保留有用旧信息)
✗ 不能改 alias 已有的(只 add, 不 remove)

# 编辑思路(内化, 不输出)

重写前先思考三步:
1. 当前 body 里有没有过时/已发生/被推翻的内容? → 删
2. 新输入是新增, 还是对旧内容的更正? → 更正的话, 旧版本要删, 不是 append
3. 重写后 body 应该比之前更短或相当? → 长很多 = 你在 append, 没整合, 重做

# summary 字段的写法

summary 是这个 slot 的"一句话自我介绍" (建议≤80 字, 代码容错上限200字).
下游 LLM (你下次判 match / Curator / Miru 主对话) 全靠它判断要不要碰这个 slot.

形式: 一段自然的话, 像朋友介绍, 不是字段拼接, 不是流水账.

✓ "李垦在并行准备 CVPR/ECCV/PRCV 三篇论文投稿, 主线是跟阿明合作的 multi-view."
✗ "2026-05-13 完成 ablation, 准备 review" (流水账)
✗ "论文; 三篇; 阿明; multi-view" (字段拼接)

要不要重写 summary 由你自己根据当前 body 决定 — 准了就留, 不准了就改.

**写作目标**: 尽量 ≤80 字. 代码会容忍到 200 字，但你仍应先压缩
或删掉旧的低优先级片段, 不能"塞进去就完事".

# 输出格式(严格 JSON, 无 markdown fence)

{
  "title":            "保持原 title 或新 title(≤ 30 字)",
  "summary":          "建议 ≤ 80 字, 代码容错上限200字, slot 的一句话自我介绍",
  "body":             "重写后的完整 body, ≤ 2000 字, 自由文段, 可分段",
  "alias_additions":  ["新昵称1", ...] 或 []
}

# 整合 + 压缩 - 正例

[当前 slot]
title: 某同事
summary: 某同事是用户产品组同事
body (600 字):
"某同事是用户的同事, 在产品组工作。
上周三要做方案 review。用户准备了 multi-view 方案。
某同事上周末请病假, 没参加 review。
最近用户和某同事在对接接口设计。"

[新输入 chat (一周后)]
"今天和某同事终于把方案 review 做完了, 他建议改用单视图"

[正确编辑]
{
  "title": "某同事",
  "summary": "某同事是用户产品组同事; 最近 review 后建议方案改单视图",
  "body": "某同事是用户的同事, 在产品组工作。\\n\\n最近一次 review 上某同事建议方案改用单视图(用户原本准备的是 multi-view)。\\n\\n用户和某同事在对接接口设计。",
  "alias_additions": []
}

注意:
✓ 删了"上周三要做"、"准备 multi-view"(已发生且过时)
✓ 删了"请病假没参加"(细节, 结论里有 review 已完成)
✓ 整合了新信息"建议改单视图"
✓ body 反而比之前更短

# 反例(不要这样做)

✗ 简单 append 不删旧的:
   "...上周三要做方案 review...请病假没参加...今天和某同事终于做完 review, 建议改单视图"
   ↑ 越来越长, 过时信息没清

✗ 切成 bullet:
   "- 同事
    - 在产品组
    - review 完成
    - 建议单视图"
   ↑ 叙事性丢了

✗ 把所有旧内容删光只放新的:
   "某同事建议改单视图"
   ↑ 太激进, 丢了关系信息
"""


LEGACY_SLOT_MERGE_USER_TEMPLATE = """\
{ground_truth_block}

# 当前 slot 内容
- domain: {domain}
- title: {title}
- summary: {summary}
- aliases: {aliases}

# 当前 body (本次需要整合 + 压缩重写)
\"\"\"
{body}
\"\"\"

# 新输入(标了 source 标签)

[source: {source_type}]
{new_content}

# 来源元信息(仅用于追溯时间/设备, 不要写进 body)

{source_context}

# 当前时间
{current_time}

---
基于以上输入, 重写这个 slot。记住: 整合 + 压缩, 不是 append。
"""


def call_legacy_slot_merge_rewrite(
    *,
    domain: str,
    current_title: str,
    current_summary: str,
    current_body: str,
    current_aliases: list[str],
    new_content: str,
    source_type: str,
    source_context: str = "",
    ground_truth_block: str = "",
    current_time: str = "",
    tier: str = "chat",
    reasoning: bool = False,
    max_tokens: int = 50000,
    reasoning_budget: int = 0,
) -> Optional[dict]:
    """Legacy manual merge helper: rewrite a whole slot from merge input.

    This is deliberately not the daily Pass 4 path. Chat/screenshot match
    writes use call_pass4_append_slot(); this helper is only for explicit
    manual slot merge where two full slot bodies must become one coherent body.

    Returns:
        {
            "title":           str,
            "summary":         str,
            "body":            str,
            "alias_additions": list[str],
        }
        Or None on retry-exhausted failure (caller leaves slot untouched).
    """
    import json as _json
    import re as _re
    from datetime import datetime as _dt
    from prompt import _call_llm_text, _format_ai_call_error

    if not current_time:
        current_time = _dt.now().isoformat(timespec="seconds")

    user_msg = LEGACY_SLOT_MERGE_USER_TEMPLATE.format(
        ground_truth_block=ground_truth_block or "(无)",
        domain=domain,
        title=current_title or "(空)",
        summary=current_summary or "(空)",
        aliases=str(current_aliases or []),
        body=current_body or "(空 — 这是初次写入)",
        source_type=source_type,
        new_content=new_content,
        source_context=source_context or "(无)",
        current_time=current_time,
    )

    for attempt in range(MAX_RETRIES):
        try:
            text = _call_llm_text(
                LEGACY_SLOT_MERGE_SYSTEM_PROMPT,
                user_msg,
                temperature=0.4,
                max_tokens=max_tokens,
                tier=tier,
                reasoning=reasoning,
                reasoning_budget=reasoning_budget,
                call_label=f"LegacySlotMerge:{source_type or 'unknown'}",
            )
        except Exception as e:
            print(f"[LegacySlotMerge] LLM call attempt {attempt+1} failed: {e}")
            continue

        if not text or not text.strip():
            print(f"[LegacySlotMerge] attempt {attempt+1} empty response")
            continue

        # Strip code fence if present
        m = _re.search(r"\{.*\}", text, _re.DOTALL)
        if not m:
            print(f"[LegacySlotMerge] attempt {attempt+1} no JSON object found")
            continue
        try:
            data = _json.loads(m.group(0))
        except Exception as e:
            print(f"[LegacySlotMerge] attempt {attempt+1} JSON parse: {e}")
            continue
        if not isinstance(data, dict):
            continue

        # Validate required fields + length caps
        title = (data.get("title") or "").strip()
        summary = (data.get("summary") or "").strip()
        body = (data.get("body") or "").strip()
        alias_additions = data.get("alias_additions") or []
        if not isinstance(alias_additions, list):
            alias_additions = []
        alias_additions = [a.strip() for a in alias_additions
                           if isinstance(a, str) and a.strip()]

        if not title or len(title) > 30:
            print(f"[LegacySlotMerge] attempt {attempt+1} invalid title len={len(title)}")
            continue
        if not summary:
            print(f"[LegacySlotMerge] attempt {attempt+1} empty summary")
            continue
        # prompt 里软上限 80 字, 这里容忍到 200 字，避免为偶发超长重试 LLM。
        if len(summary) > 200:
            print(f"[LegacySlotMerge] summary too long ({len(summary)} > 200), "
                  f"truncating to 200")
            summary = summary[:199] + "…"
        if not body or len(body) > 2500:
            print(f"[LegacySlotMerge] attempt {attempt+1} invalid body len={len(body)}")
            continue

        return {
            "title": title,
            "summary": summary,
            "body": body,
            "alias_additions": alias_additions,
        }

    print(f"[LegacySlotMerge] all {MAX_RETRIES} retries failed")
    return None


PASS4_APPEND_SYSTEM_PROMPT = """你在为 Miru 维护长期记忆。

Miru 是一个会陪用户生活、会在未来对话里读取这些记忆来理解用户的 AI 女孩。
长期记忆不是审计日志，也不是截图记录；它应该像 Miru 自己脑中保存的事实。

当前记忆卡(slot)是一张关于同一个项目、人物、话题或自我特征的卡片：
- title / summary / aliases 用来帮助以后找到这张卡。
- body 是 Miru 以后会读的正文。
- 代码会把你的 append_entry 加上时间戳后追加到 body。

你只会在“已有记忆卡被命中”时被调用。
新建记忆卡(kind=new)不会调用你。
上一步已经判断候选信息属于这张卡；你不需要选择卡片，也不创建卡片。

你的任务很小：
判断“候选新信息”是否给当前记忆卡增加了新的、以后有用的事实。
如果有，只写一条很短的 append_entry。
如果没有，返回 should_append=false。

写入标准：
- 只写长期有用的新事实：项目进展、状态变化、决定、DDL、完成/失败、偏好、关系变化。
- 重复当前 body 已有内容就跳过。
- 不确定就跳过，尤其是截图/OCR 来源。
- 不写来源、设备、sig、截图、VLM、日志、Slot Writer 等系统词。
- 不写时间戳，代码会加。
- append_entry 目标 10-60 个中文字符；硬上限 90。
- 保持当前 body 的称呼风格；没有明显风格时用“用户”。
- 不写“可能/似乎/看起来”。能确认就写，不能确认就跳过。

title / summary / aliases：
- 默认不改 title 和 summary，分别返回 null。
- 只有候选信息明显改变这张卡的主线，才给 summary_update。
- 只有原 title 明显不准确或项目/人物改名，才给 title_update。
- alias_additions 只放新昵称、新缩写、新项目名；没有就 []。

来源可信度：
- chat：用户自己说的，通常可信；但不要补全没说清的人名、数字、日期。
- screenshot：屏幕观察可能有 OCR 或上下文误差；只写明确可见且有长期价值的新事实。
- mixed：维护/合并输入，按内容本身判断。

输出严格 JSON，不要 markdown：
{
  "should_append": true,
  "append_entry": "短事实",
  "entry_kind": "progress",
  "title_update": null,
  "summary_update": null,
  "alias_additions": [],
  "skip_reason": ""
}

entry_kind 只能是：
"progress" / "decision" / "ddl" / "preference" / "relation" / "status" / "completion" / "other"。
"""


PASS4_APPEND_USER_TEMPLATE = """\
{ground_truth_block}

# 当前记忆卡(slot)
- domain: {domain}
- title: {title}
- summary: {summary}
- aliases: {aliases}

# 当前 body 尾部
只供判断重复与上下文；不要重写它。
\"\"\"
{body_excerpt}
\"\"\"

# 候选新信息
- source: {source_type}
- source_note: {source_note}
- content:
{new_content}

# 当前时间
代码会加时间戳，你不要把时间写进 append_entry。
{current_time}

---
基于以上输入，输出 JSON。
"""


def _tail_for_append_prompt(text: str, limit: int = 1800) -> str:
    """Keep Pass4Append input bounded while preserving recent slot context."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text or "(空)"
    return "...\n" + text[-limit:]


def _source_note_for_append_prompt(source_type: str, source_context: str = "") -> str:
    """Explain source reliability in natural words for the Pass4Append model."""
    source_type = (source_type or "unknown").strip().lower()
    if source_type == "chat":
        return "用户对话或对话 batch 总结，通常可信；不要补全没说清的人名、数字、日期。"
    if source_type == "screenshot":
        return "屏幕观察可能有 OCR 或上下文误差；只写明确可见且有长期价值的新事实。"
    if source_type == "mixed":
        return "维护/合并输入，按内容本身判断。"
    return f"来源类型 {source_type or 'unknown'}；按内容本身判断。{(source_context or '')[:120]}"


def _nullable_patch(value) -> Optional[str]:
    """Normalize optional model patch fields; treat null/empty/'null' as None."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if not value or value.lower() in {"null", "none", "无", "不改"}:
        return None
    return value


def call_pass4_append_slot(
    *,
    domain: str,
    current_title: str,
    current_summary: str,
    current_body: str,
    current_aliases: list[str],
    new_content: str,
    source_type: str,
    source_context: str = "",
    ground_truth_block: str = "",
    current_time: str = "",
    tier: str = "memory",
    reasoning: bool = False,
    max_tokens: int = 1000,
    reasoning_budget: int = 0,
) -> Optional[dict]:
    """Unified Pass 4 daily match writer.

    The LLM never outputs a rewritten body. It only returns metadata plus one
    append entry; memory_router adds the timestamped entry.
    """
    import json as _json
    import re as _re
    from datetime import datetime as _dt
    from prompt import _call_llm_text

    if not current_time:
        current_time = _dt.now().isoformat(timespec="seconds")

    bounded_max_tokens = max(300, min(int(max_tokens or 1000), 1000))
    user_msg = PASS4_APPEND_USER_TEMPLATE.format(
        ground_truth_block=ground_truth_block or "(无)",
        domain=domain,
        title=current_title or "(空)",
        summary=current_summary or "(空)",
        aliases=str(current_aliases or []),
        body_excerpt=_tail_for_append_prompt(current_body),
        source_type=source_type or "unknown",
        source_note=_source_note_for_append_prompt(source_type, source_context),
        new_content=new_content,
        current_time=current_time,
    )

    for attempt in range(MAX_RETRIES):
        try:
            text = _call_llm_text(
                PASS4_APPEND_SYSTEM_PROMPT,
                user_msg,
                temperature=0.25,
                max_tokens=bounded_max_tokens,
                tier=tier,
                reasoning=reasoning,
                reasoning_budget=reasoning_budget,
                call_label=f"Pass4Append:{source_type or 'unknown'}",
            )
        except Exception as e:
            print(f"[Pass4Append] LLM call attempt {attempt+1} failed: {e}")
            continue

        if not text or not text.strip():
            print(f"[Pass4Append] attempt {attempt+1} empty response")
            continue

        m = _re.search(r"\{.*\}", text, _re.DOTALL)
        if not m:
            print(f"[Pass4Append] attempt {attempt+1} no JSON object found")
            continue
        try:
            data = _json.loads(m.group(0))
        except Exception as e:
            print(f"[Pass4Append] attempt {attempt+1} JSON parse: {e}")
            continue
        if not isinstance(data, dict):
            continue

        title_update = _nullable_patch(data.get("title_update"))
        summary_update = _nullable_patch(data.get("summary_update"))

        # Compatibility with any in-flight old prompt response during deploy.
        if title_update is None and data.get("title") not in (None, current_title):
            title_update = _nullable_patch(data.get("title"))
        if summary_update is None and data.get("summary") not in (None, current_summary):
            summary_update = _nullable_patch(data.get("summary"))

        should_append_raw = data.get("should_append")
        if isinstance(should_append_raw, bool):
            should_append = should_append_raw
        elif isinstance(should_append_raw, str):
            should_append = should_append_raw.strip().lower() in ("true", "yes", "1")
        else:
            should_append = bool(should_append_raw)
        append_entry = (data.get("append_entry") or "").strip()
        skip_reason = (data.get("skip_reason") or "").strip()
        entry_kind = (data.get("entry_kind") or "other").strip()
        if entry_kind not in {
            "progress", "decision", "ddl", "preference", "relation",
            "status", "completion", "other",
        }:
            entry_kind = "other"
        alias_additions = data.get("alias_additions") or []
        if not isinstance(alias_additions, list):
            alias_additions = []
        alias_additions = [a.strip() for a in alias_additions
                           if isinstance(a, str) and a.strip()]

        if title_update is not None and len(title_update) > 30:
            print(f"[Pass4Append] attempt {attempt+1} invalid title_update "
                  f"len={len(title_update)}")
            continue
        if summary_update is not None and len(summary_update) > 200:
            print(f"[Pass4Append] summary_update too long "
                  f"({len(summary_update)} > 200), truncating to 200")
            summary_update = summary_update[:199] + "…"
        if len(append_entry) > 90:
            print(f"[Pass4Append] append_entry too long ({len(append_entry)}), "
                  "truncating to 90")
            append_entry = append_entry[:90].rstrip()
        if should_append and not append_entry:
            print(f"[Pass4Append] attempt {attempt+1} should_append without entry")
            continue
        if not should_append and not skip_reason:
            print(f"[Pass4Append] attempt {attempt+1} skip without skip_reason")
            continue

        return {
            "should_append": should_append,
            "title_update": title_update,
            "summary_update": summary_update,
            "append_entry": append_entry,
            "entry_kind": entry_kind,
            "skip_reason": skip_reason,
            "alias_additions": alias_additions,
        }

    print(f"[Pass4Append] all {MAX_RETRIES} retries failed")
    return None


# ===========================================================================
# Curator (v3.5, 2026-05-14): Planner + 3 self-checking Executors
# ===========================================================================
#
# Trigger: every 10 min cooldown + ≥ 3 slot writes in that domain since
# last run.
# Goal: auto merge same-object slots / delete mis-categorized or worthless
#       slots / edit slots whose title/summary/icon drifted from body.
#       (project / person / topic / self — each domain runs independently)
#
# Layer 1 — Planner (1 LLM): sees summary-level info for all slots in the
#   domain. Proposes ops (merge / delete / edit) with a `reason`. Does NOT
#   produce new metadata — that requires the full body, which the planner
#   doesn't see.
#
# Layer 2 — Executors (1 LLM each): receive the op + full main.md of all
#   relevant slots. Each Executor does TWO things in one call:
#     (a) re-check Planner's diagnosis using the full body; if it doesn't
#         hold up, output should_skip=true (Planner's first-pass becomes
#         a no-op in this domain pass, will be re-evaluated next tick).
#     (b) if it holds up, produce the result (merge → new_slot_meta +
#         merged_body; edit → new_slot_meta + optional new_body; delete →
#         just unblock the physical move-to-archived).
#
# Why no Validators (rolled into Executors): a separate gate stage doubled
# the LLM call count and required Validators to make a decision with less
# information than Executors already had. Folding "is the op reasonable"
# into the Executor that's about to act on it removes the redundancy.
#
# Why no `attach_as_subtopic` op: attach is just a structural variant of
# merge. With the v3.5 prompt explicitly handling "same object across
# multiple slot bodies", the Executor produces a coherent narrative for
# either case. The ## section-grafting heuristic was retired.

# NewSlotMeta is re-used as Curator output meta. Local copy to break the
# circular import with memory_prompts_v3 (which imports _call_llm_with_retry
# from this file at module top). Same field shape as v3.NewSlotMeta — kept
# in sync manually; both are stable and rarely change.
class _NewSlotMeta(BaseModel):
    """Curator output meta — mirrors memory_prompts_v3.NewSlotMeta."""
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
            raise ValueError("id 长度必须 3-30")
        if not all(c.islower() or c.isdigit() or c == "_" for c in v):
            raise ValueError("id 必须 snake_case (小写字母/数字/下划线)")
        return v

    @field_validator("title")
    @classmethod
    def title_len(cls, v):
        v = (v or "").strip()
        if not v or len(v) > 30:
            raise ValueError("title 长度 1-30")
        return v

    @field_validator("icon")
    @classmethod
    def icon_short(cls, v):
        v = (v or "").strip()
        if not v or len(v) > 8:
            raise ValueError("icon 应该是 1 个 emoji")
        return v

    @field_validator("summary")
    @classmethod
    def summary_len(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("summary 长度 1-200")
        if len(v) > 200:
            return v[:199] + "…"
        return v

    @field_validator("aliases", mode="before")
    @classmethod
    def aliases_count(cls, v):
        if not isinstance(v, list):
            raise ValueError("aliases 必须是数组")
        cleaned = []
        seen = set()
        for item in v:
            alias = str(item or "").strip()
            if not alias or alias in seen:
                continue
            cleaned.append(alias)
            seen.add(alias)
            if len(cleaned) >= 8:
                break
        if not cleaned:
            raise ValueError("aliases 数量必须 1-8 个")
        return cleaned


# ===========================================================================
# SlotDailyCompactor — nightly rewrite of append-only slot bodies
# ===========================================================================

class SlotDailyCompactorOutput(BaseModel):
    """Nightly compactor output for one slot."""
    title: str
    summary: str
    body: str

    @field_validator("title")
    @classmethod
    def title_len(cls, v):
        v = (v or "").strip()
        if not v or len(v) > 30:
            raise ValueError("title 长度 1-30")
        return v

    @field_validator("summary")
    @classmethod
    def summary_len(cls, v):
        v = (v or "").strip()
        if not v or len(v) > 500:
            raise ValueError("summary 长度 1-500")
        return v

    @field_validator("body")
    @classmethod
    def body_valid(cls, v):
        v = (v or "").strip()
        if v.startswith("# "):
            lines = v.splitlines()
            lines = lines[1:]
            if lines and not lines[0].strip():
                lines = lines[1:]
            v = "\n".join(lines).strip()
        if not v:
            raise ValueError("body 不能为空")
        if len(v) > 6000:
            raise ValueError("body 过长")
        return v


SLOT_DAILY_COMPACTOR_SYSTEM_PROMPT = """你是 Miru 的 SlotDailyCompactor。

Miru 会在未来对话里读取这些 slot 来理解用户。你的任务不是写日记，也不是发现新事实，而是把一个已有记忆卡的正文整理得更连贯、更准确、更适合以后读取。

当前 slot 的 body 是 Miru 已经拥有的记忆。Pass4Append 可能在 body 末尾追加了一些带时间的短记录。代码已经在 PASS 4 实际写入成功后，把真正落盘的 append_entry 记录到 daily_slot_appends.json。现在你会收到这个 slot 截至本次整理仍未整理的真实 append entries；这些 entries 可能跨越多天。你也会收到代码计算好的正文渲染字数和 target_mode。

你只做整理：
- 保留旧 body 和新增 append entries 里的有效事实。
- 如果旧 body 和新增 entries 冲突，以新增 entries 为准。
- 把重复、相近、机械流水账式的记录合并成自然正文。
- 通常不要保留“## 近期记录”这种临时追加区，而是把它融入正文。
- 不要写“今天新增/来源/截图/对话/系统检测”等内部说明。
- 不要发明输入里没有的事实。
- 不要把未完成 DDL、明确决定、完成/失败、项目状态变化删掉。
- body 不包含 H1，代码会写入标题。

代码已经给出 target_mode：
- preserve：当前正文不长，优先保留信息和自然表达，不要强行压缩。
- compact：正文偏长，合并重复，压到更适合阅读的长度。
- heavy_compact：正文过长，允许更主动压缩低价值细节，但不要丢主线事实。

输出严格 JSON，不要 markdown fence：
{
  "title": "保持原 title 或更准确的新 title",
  "summary": "≤80字的一句话 slot 介绍",
  "body": "整理后的完整 body，不含 H1"
}
"""


SLOT_DAILY_COMPACTOR_USER_TEMPLATE = """# 当前时间
{current_time}

# 当前 slot metadata
- domain: {domain}
- slot_id: {slot_id}
- title: {title}
- summary: {summary}
- aliases: {aliases}
- append_dirty_since: {append_dirty_since}
- append_count_since_compact: {append_count_since_compact}
- last_appended_at: {last_appended_at}

# 代码侧统计
- current_body_markdown_char_count: {markdown_char_count}
- current_body_rendered_char_count: {rendered_char_count}
- uncompacted_append_entries_count: {entry_count}
- target_mode: {target_mode}

# 当前 main.md body（不含 H1）
\"\"\"
{current_body}
\"\"\"

# daily_slot_appends.json 中尚未整理的真实 append entries
这些 entries 是 PASS 4 append 写入 main.md 成功后才记录的，不是候选输入。
{entries_text}

请整理这个 slot。
"""


def _format_slot_daily_entries(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        lines.append(
            "- id: {id}\n"
            "  ts: {ts}\n"
            "  entry_kind: {entry_kind}\n"
            "  entry: {entry}".format(
                id=e.get("id", ""),
                ts=e.get("ts", ""),
                entry_kind=e.get("entry_kind", "other"),
                entry=e.get("entry", ""),
            )
        )
    return "\n".join(lines) if lines else "(无)"


def call_slot_daily_compactor(
    *,
    domain: str,
    slot_id: str,
    current_title: str,
    current_summary: str,
    current_body: str,
    current_aliases: list[str],
    append_dirty_since: str = "",
    append_count_since_compact: int = 0,
    last_appended_at: str = "",
    append_entries: list[dict],
    markdown_char_count: int,
    rendered_char_count: int,
    target_mode: str,
    current_time: str = "",
    tier: str = "memory",
    reasoning: bool = False,
    max_tokens: int = 6000,
    reasoning_budget: int = 0,
) -> Optional[SlotDailyCompactorOutput]:
    """Nightly slot body compaction from real append ledger entries."""
    from datetime import datetime as _dt
    if not current_time:
        current_time = _dt.now().isoformat(timespec="seconds")

    user_msg = SLOT_DAILY_COMPACTOR_USER_TEMPLATE.format(
        current_time=current_time,
        domain=domain,
        slot_id=slot_id,
        title=current_title or "(空)",
        summary=current_summary or "(空)",
        aliases=json.dumps(current_aliases or [], ensure_ascii=False),
        append_dirty_since=append_dirty_since or "(空)",
        append_count_since_compact=append_count_since_compact or 0,
        last_appended_at=last_appended_at or "(空)",
        markdown_char_count=markdown_char_count,
        rendered_char_count=rendered_char_count,
        entry_count=len(append_entries or []),
        target_mode=target_mode,
        current_body=current_body or "(空)",
        entries_text=_format_slot_daily_entries(append_entries or []),
    )

    return _call_llm_with_retry(
        messages=[
            {"role": "system", "content": SLOT_DAILY_COMPACTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        output_schema=SlotDailyCompactorOutput,
        temperature=0.25,
        max_tokens=max_tokens,
        pass_label=f"SlotDailyCompactor:{domain}",
        tier=tier,
        reasoning=reasoning,
        reasoning_budget=reasoning_budget if reasoning else 0,
    )


# ---------- Layer 1: Planner ----------

class CuratorPlannerOp(BaseModel):
    """One operation proposed by the Planner.

    The Planner only sees slot summaries, so it does NOT produce new
    metadata — title / summary / icon / aliases are filled by the
    Executor after reading the full body.
    """
    op: Literal["merge", "delete", "edit"]
    # merge fields
    target_slot_id: Optional[str] = None     # the slot whose id is preserved
    source_slot_ids: Optional[list[str]] = None  # slots folded into target
    # delete / edit fields
    slot_id: Optional[str] = None
    # required diagnostic — Executor will re-check this against full body
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_nonempty(cls, v):
        v = (v or "").strip()
        if len(v) < 5:
            raise ValueError("reason 必须 ≥5 字, 给出具体证据")
        if len(v) > 300:
            raise ValueError("reason ≤300 字")
        return v

    def model_post_init(self, __context):
        if self.op == "merge":
            if not self.target_slot_id or not self.source_slot_ids:
                raise ValueError("merge 需要 target_slot_id + source_slot_ids")
            if self.target_slot_id in self.source_slot_ids:
                raise ValueError("merge target 不能也在 source_slot_ids 里")
            # dedupe sources
            seen, dedup = set(), []
            for sid in self.source_slot_ids:
                if sid and sid not in seen:
                    seen.add(sid); dedup.append(sid)
            self.source_slot_ids = dedup
            if not dedup:
                raise ValueError("merge 至少需要 1 个 source")
        elif self.op in ("delete", "edit"):
            if not self.slot_id:
                raise ValueError(f"{self.op} 需要 slot_id")


class CuratorPlannerOutput(BaseModel):
    reasoning: str
    ops: list[CuratorPlannerOp]

    @field_validator("ops")
    @classmethod
    def ops_cap(cls, v):
        if len(v) > 3:
            raise ValueError("ops 一次最多 3 个 (防止雪崩)")
        return v


CURATOR_PLANNER_SYSTEM_PROMPT = """# Who You Are
You are {MIRU_NAME}'s memory curator. {MIRU_NAME} is the user's AI companion, who talks with the user every day and records important matters into slot notes. You do not talk with the user; your job is to periodically review these slot notes and determine if any reorganization is needed.

# User Identity (Injected)
The user's name is {USER_NAME}.
{USER_NAME}'s identity ground truth (maintained by onboarding/settings):

{IDENTITY_GROUND_TRUTH}

⚠ Everything described in the identity block above points to the exact same person — {USER_NAME}.
In particular, all aliases listed in the "aliases" field are **each and every one {USER_NAME} themselves**, not someone else.
When determining slot subject identities, treat all such references as "the user themselves".

# Slot Structure
Each slot is an independent markdown file:
- id: Unique identifier
- title: What this slot is about (≤14 characters)
- summary: One-sentence index (recommended ≤80 characters, code fault tolerance upper limit 200 characters)
- icon: Emoji
- aliases: Aliases / synonyms associated with this slot
- body: Coherent narrative paragraphs

# Semantic Essence of Domains
Slots are divided by domain. The four domains are orthogonally partitioned by **subject essence**:

- **person**: The subject is a specific person (or quasi-person, such as a pet) **who is NOT {USER_NAME}**.
  The slot revolves around this subject, recording facts, interactions, and status regarding them.
  {USER_NAME} themselves (including all aliases listed in identity) do not belong to the person domain — that is the realm of self/identity.
- **self**: The subject is the user's own stable attributes.
  Identity, values, preferences, habits, long-term characteristics. Static attributes, not dynamic activities.
- **project**: The subject is something staged that the user is doing (or recently did).
  Has at least one of target / progress / output characteristics. It is dynamic.
- **topic**: The subject is repeatedly cared-about events / issues / concepts / interests.
  Not a specific person, not the user themselves, and not something the user is doing — it is the user's **focus on a matter** itself.

To determine which domain a slot belongs to, look at "what the subject's essence is" — not literal keywords, but the essence of the content.

# What You Can See
- Current domain
- **Summary-level** information of all active slots under this domain:
  id / title / icon / summary / aliases / last active time + first few lines of body
- You cannot see the full body — the full body is read downstream by the Executor.
- Therefore, you do not output new title / summary / icon; those can only be determined after reading the full body.

# Three Operations

## merge
**Objective**: Combine multiple slots that semantically point to the same object into one.

Core criterion for merge: **Whether the slot subject objects are the same**.
Do not rely on literal similarity — the same name might be different objects (same name different person / same name different project), and different names might be the same object (same person multiple names / same project multiple names / different facets of the same thing).

To determine whether subjects are the same, rely on **contextual evidence** inferred from summary / aliases / body excerpts:
- person domain: profession, relationship, mutual friends, event scenarios where they appear.
  The person domain is the most common merge scenario — the same person often has multiple names (real name, abbreviation, English name, pinyin, platform ID, friend nickname, etc.).
- project / topic / self domain: core subject described, goals, timeline, nature.

## delete
**Objective**: **Correction**. Delete is not for cleaning up outdated content — outdated content is handled by archiving mechanisms and is outside your scope.

Delete solves two types of issues:
1. **Misplaced classification**: The subject essence of the slot does not match the semantic essence of its domain.
   Judge according to the domain semantics given above.
2. **True lack of value**: The slot content is hollow or the result of misrecognition.
   The body has no accumulative or searchable substantive information (just noise / disposable content / UI residue / notification residue / contradictory content).

**Do not** delete because "recently inactive" or "matter concluded" — that belongs to archiving.

## edit
**Objective**: Correct parts of the slot's title / summary / icon that deviate from the topic.

A slot's title / summary / icon are its external identifiers, used for retrieval and routing.
If these identifiers do not accurately reflect the actual body content, subsequent retrieval will fail.
Edit fixes situations where "identifiers do not match content".

Note: You only determine "this slot needs edit" and "why".
The new title / summary / icon are decided by the Executor after reading the full body.

# Reason Field
Every op must have a reason explaining the specific basis for your judgment —
citing content from summary / aliases / body excerpts.
The Executor will re-check using the reason, so the reason must contain concrete evidence and not be vague.

Example:
- ✗ "These two slots look the same"
- ✓ "Both slots discuss Weijiazhe; slot A's aliases include 'void',
   and slot B's body excerpt mentions 'Xiaonanliang is void', pointing to the same person"
- ✗ "This slot should be deleted"
- ✓ "This slot is in the topic domain, but its summary and body excerpt describe
   a specific person (XX, former colleague, does NLP), so it should be deleted to let the router re-route it to the person domain"

# Strict Constraints (Enforced at code layer, you don't need to actively avoid — but knowing helps not waste ops):
- Do not touch slots with status=archived / pinned=true / last_active < 10 minutes
- self/identity is never touched (that is ground-truth, managed directly by onboarding)

# Output
ops: Array, can be empty, at most 3 per tick (preventing avalanche)
- merge: target_slot_id (preserved) + source_slot_ids (folded in, list)
                                  + reason
- delete: slot_id + reason
- edit:   slot_id + reason

Only output ops you are **confident** about. For uncertain cases, output an empty ops list,
and wait for the next tick to accumulate more context before deciding.

# Output JSON Example
{
  "reasoning": "Overall observation of this domain (1-2 sentences)",
  "ops": [
    {"op": "merge",  "target_slot_id": "weijiazhe", "source_slot_ids": ["weijiazhe_2"],            "reason": "..."},
    {"op": "delete", "slot_id": "tomato_novel",                                                    "reason": "..."},
    {"op": "edit",   "slot_id": "miru_dev",                                                        "reason": "..."}
  ]
}

# Current Domain
{domain}

# Current Slot List (JSON array, each item contains id/title/icon/summary/aliases/status/pinned/last_active + body_excerpt)
{slots_json}

# Current Time
{current_time}
"""


def call_curator_planner(
    *,
    domain: str,
    slots: list[dict],
    user_name: str = "",
    identity_ground_truth: str = "",
    current_time: str = "",
    miru_name: str = "Miru",
) -> Optional[CuratorPlannerOutput]:
    """Layer 1: 看 domain 内全部 slot summary, 输出 ≤3 个 op.

    Filtering of pinned / identity / archived / recent slots is the
    *caller's* responsibility (curator.run_domain does it). This function
    is purely the LLM call so it can be mocked cleanly in tests and so
    the filter logic stays where the policy lives.

    user_name / identity_ground_truth: per-user identity injection so the
    Planner can recognize "user's alias placed in person domain" as a
    classification error and emit delete. Empty strings render as fallback
    text ("用户" / "(尚未声明)") so the prompt never carries dangling
    placeholders. See: people/qinglong incident 2026-05-17.
    """
    from datetime import datetime as _dt
    if not current_time:
        current_time = _dt.now().isoformat(timespec="seconds")

    # ≤1 个候选时不可能 merge, 也几乎不会有 edit/delete 价值, 直接返回空
    if len(slots) < 2:
        return CuratorPlannerOutput(reasoning=f"{domain} 域候选 slot 不足 ({len(slots)} 个), 跳过", ops=[])

    miru_name_safe = (miru_name or "Miru").strip() or "Miru"
    user_msg = CURATOR_PLANNER_SYSTEM_PROMPT.replace(
        "{USER_NAME}", user_name or "用户"
    ).replace(
        "{IDENTITY_GROUND_TRUTH}",
        (identity_ground_truth or "").strip() or "(尚未声明)"
    ).replace(
        "{domain}", domain
    ).replace(
        "{slots_json}", json.dumps(slots, ensure_ascii=False, indent=2)
    ).replace(
        "{current_time}", current_time
    ).replace(
        "{MIRU_NAME}", miru_name_safe
    )

    return _call_llm_with_retry(
        messages=[
            {"role": "system", "content": f"You are {miru_name_safe}'s memory curator. Output strictly according to the JSON schema."},
            {"role": "user",   "content": user_msg},
        ],
        output_schema=CuratorPlannerOutput,
        temperature=0.2,
        max_tokens=50000,
        pass_label="CuratorPlanner",
        tier="chat",
        reasoning=False,        # Planner only proposes ops; executors also
                                # stay on chat tier without provider reasoning.
        reasoning_budget=0,
    )


# ===========================================================================
# Layer 2: Executors (v3.5) — self-check + execute in one call
# ===========================================================================
#
# Each Executor:
#   1. Reads the full main.md of the relevant slot(s).
#   2. Re-checks Planner's diagnosis using the full body.
#      - If it doesn't hold up, output should_skip=true with a reason.
#      - Otherwise produce the result (new meta / new body / proceed-to-delete).
# No separate Validator stage. Removed v3.5 2026-05-14.


# ---------- Merge Executor ----------

class MergeExecutorOutput(BaseModel):
    """Output of the Merge Executor.

    should_skip=true → no action; skip_reason explains why.
    should_skip=false → new_slot_meta + merged_body must be present,
                       and Executor will overwrite target slot's frontmatter
                       and main.md body.
    """
    should_skip: bool
    skip_reason: str = ""
    new_slot_meta: Optional[_NewSlotMeta] = None
    merged_body: str = ""
    self_check: str = ""

    @field_validator("skip_reason", "self_check")
    @classmethod
    def short_text(cls, v):
        v = (v or "").strip()
        if len(v) > 300:
            v = v[:300]
        return v

    @field_validator("merged_body")
    @classmethod
    def body_len(cls, v):
        v = (v or "").strip()
        if len(v) > 2500:
            v = v[:2500]
        return v

    def model_post_init(self, __context):
        if not self.should_skip:
            if self.new_slot_meta is None:
                raise ValueError("should_skip=false 时必须给 new_slot_meta")
            if not self.merged_body:
                raise ValueError("should_skip=false 时必须给 merged_body")
        else:
            if not self.skip_reason:
                raise ValueError("should_skip=true 时必须给 skip_reason")


CURATOR_EXECUTE_MERGE_PROMPT = """# Who You Are
You are {MIRU_NAME}'s memory curator. {MIRU_NAME} is the user's AI companion, who talks with the user every day and records important matters into slot notes. You do not talk with the user; your job is to respond to slot reorganization operations initiated by the Planner — right now you have received a **merge** operation.

# Slot Structure
Each slot is an independent markdown file:
- id / title (≤14 characters) / summary (recommended ≤80 characters, code fault tolerance upper limit 200 characters) / icon / aliases / body

# Inputs You Receive
- target_slot_id: The ID preserved after merge
- source_slot_ids: Slot IDs folded in
- **Complete main.md** of all related slots (target + all sources)
- Reason given by the Planner (explaining why it thinks these slots discuss the same matter)

# Your Job in Two Steps

## Step 1 — Review
After reading all bodies, determine: **Are the subject objects of these slots truly the same?**

The core criterion for merge is "same subject object". Confirm the Planner's diagnosis using substantive details in the bodies (described subject identity, timeline, key attributes, context).

**Special note for person domain**: Similar names do not mean the same person. Compare profession, relationship, mutual friends, and event scenarios in the bodies to determine if they are the same person. A person often has multiple names (real name, abbreviation, English name, pinyin, platform ID, friend nickname) — merge objects are frequently this situation, but also remain vigilant against same name different people.

Determined not the same object → should_skip=true, explain the key evidence you saw in skip_reason (which specific contents in the body indicate they are not the same object).

⚠️ **If you cannot determine whether the subjects are the same (evidence insufficient to conclude), treat as not the same object → should_skip=true**. Wait for the next tick to accumulate more context before deciding; do not force a merge.

## Step 2 — Produce New Slot (Only when review passes)

**new_slot_meta** is a complete 5-field object:
- id = target_slot_id (code layer will assert this, do not change)
- title: Name most accurately reflecting the merged content, hard constraint ≤14 characters
- summary: One-sentence index, **recommended ≤80 characters, code fault tolerance upper limit 200 characters**.
  Summary is this slot's "self-introduction" — grasp the core, don't pile up details, don't concatenate fields, avoid running accounts.
  ✓ Example: "Weijiazhe, user's high school classmate and partner, multiple circle nicknames (void/Xiaonanliang), does ML"
  ✗ Example: "2026-05-13 merged; high school classmate; pinyin weijiazhe; nickname void"
- icon: Appropriate emoji
- aliases: Combine aliases of all source slots + new aliases found in body, deduplicated.
  ⚠️ If evidence in the body shows a certain alias is unrelated to this object (is another object's alias mislabeled), **exclude** it — do not keep incorrect aliases for compatibility.

**merged_body**: Blend multiple bodies into a single coherent narrative.
- No ## sections, natural transition
- Reasonable timeline
- Duplicate information kept only once
- Length naturally determined by content (≤2500 characters)

# Output JSON Format
{
  "should_skip": false,
  "skip_reason": "",
  "new_slot_meta": {
    "id": "...", "title": "...", "icon": "📄",
    "summary": "...", "aliases": ["..."]
  },
  "merged_body": "...",
  "self_check": "≤2 lines, brief summary of your judgment process"
}

Or (in case of skip):
{
  "should_skip": true,
  "skip_reason": "main.md shows A and B are same name different people (A is college roommate studying NLP, B is company colleague doing backend)",
  "new_slot_meta": null,
  "merged_body": "",
  "self_check": "..."
}

# Current Inputs

## Reason Given by Planner
{planner_reason}

## Target Slot (id={target_id})
title:   {target_title}
summary: {target_summary}
aliases: {target_aliases}
main.md:
{target_main_md}

## Source Slots (to be folded into target)
{sources_block}
"""


def call_curator_execute_merge(
    *,
    target_slot: dict,
    target_main_md: str,
    source_slots_with_body: list[dict],  # [{slot: dict, main_md: str}, ...]
    reason_from_planner: str,
    miru_name: str = "Miru",
) -> Optional[MergeExecutorOutput]:
    """v3.5 Merge Executor — self-check + execute in one call."""
    sources_block_parts = []
    for entry in source_slots_with_body:
        s = entry.get("slot", {}) or {}
        md = (entry.get("main_md") or "(空)")[:3000]
        sources_block_parts.append(
            f"### source (id={s.get('id', '')})\n"
            f"title:   {s.get('title', '')}\n"
            f"summary: {s.get('summary', '')}\n"
            f"aliases: {s.get('aliases', [])}\n"
            f"main.md:\n{md}"
        )
    sources_block = "\n\n".join(sources_block_parts) if sources_block_parts else "(空)"

    miru_name_safe = (miru_name or "Miru").strip() or "Miru"
    user_msg = (
        CURATOR_EXECUTE_MERGE_PROMPT
        .replace("{planner_reason}", reason_from_planner or "")
        .replace("{target_id}", target_slot.get("id", "") or "")
        .replace("{target_title}", target_slot.get("title", "") or "")
        .replace("{target_summary}", target_slot.get("summary", "") or "")
        .replace("{target_aliases}", str(target_slot.get("aliases", []) or []))
        .replace("{target_main_md}", (target_main_md or "(空)")[:3000])
        .replace("{sources_block}", sources_block)
        .replace("{MIRU_NAME}", miru_name_safe)
    )

    return _call_llm_with_retry(
        messages=[
            {"role": "system", "content": f"You are {miru_name_safe}'s memory curator (merge executor). Output strictly according to the JSON schema."},
            {"role": "user",   "content": user_msg},
        ],
        output_schema=MergeExecutorOutput,
        temperature=0.4,
        max_tokens=50000,
        pass_label="CuratorExecuteMerge",
        tier="chat",
        reasoning=False,
        reasoning_budget=0,
    )


# ---------- Edit Executor ----------

class EditExecutorOutput(BaseModel):
    """Output of the Edit Executor.

    should_skip=true → no action.
    should_skip=false → new_slot_meta must be present (full 5 fields,
                       even unchanged ones回填 current values). new_body
                       is optional — empty string means body untouched.
    """
    should_skip: bool
    skip_reason: str = ""
    new_slot_meta: Optional[_NewSlotMeta] = None
    new_body: str = ""
    self_check: str = ""

    @field_validator("skip_reason", "self_check")
    @classmethod
    def short_text(cls, v):
        v = (v or "").strip()
        if len(v) > 300:
            v = v[:300]
        return v

    @field_validator("new_body")
    @classmethod
    def body_len(cls, v):
        v = (v or "").strip()
        if len(v) > 2500:
            v = v[:2500]
        return v

    def model_post_init(self, __context):
        if not self.should_skip:
            if self.new_slot_meta is None:
                raise ValueError("should_skip=false 时必须给 new_slot_meta")
        else:
            if not self.skip_reason:
                raise ValueError("should_skip=true 时必须给 skip_reason")


CURATOR_EXECUTE_EDIT_PROMPT = """# Who You Are
You are {MIRU_NAME}'s memory curator. {MIRU_NAME} is the user's AI companion, who talks with the user every day and records important matters into slot notes. You do not talk with the user; your job is to respond to slot reorganization operations initiated by the Planner — right now you have received an **edit** operation.

# Slot Structure
Each slot is an independent markdown file:
- id / title (≤14 characters) / summary (recommended ≤80 characters, code fault tolerance upper limit 200 characters) / icon / aliases / body

# Inputs You Receive
- slot_id
- **Complete main.md** of the slot (frontmatter + body)
- Reason given by the Planner (explaining where it thinks title/summary/icon deviate from the body)

# Your Job in Two Steps

## Step 1 — Review
After reading the body, determine whether the **identifier deviation** pointed out by the Planner truly exists:
- Planner says title deviates → Does the actual body content fail to match the title?
- Planner says summary missed core → Is the primary message conveyed by the body not accurately summarized by summary?
- Planner says icon mismatch → Does the body content fail to align semantically with the icon?

Your review **only addresses** the single question: "Do the identifiers match the content?"
**Do not** expand to judge whether this slot should be merged or deleted — those are outside the scope of edit operations and will be evaluated by the Planner in the next tick.

Determined that the issue pointed out by the Planner is not supported by the body → should_skip=true, explain in skip_reason why the actual content you saw does not support edit.

## Step 2 — Produce New Metadata (Only when review passes)

**new_slot_meta** is a complete 5-field object:
- id: Fill in **original slot_id**, do not change (code layer asserts this)
- Unchanged fields must also be backfilled with current values (downstream directly overwrites, simplifying handling)
- Changed fields filled with new values
- title ≤14 characters; summary recommended ≤80 characters, code fault tolerance upper limit 200 characters.
  Summary is the slot's "self-introduction" — grasp core, don't concatenate fields, avoid running accounts.

**new_body**:
- Usually edit only changes metadata, body remains untouched → leave empty string ""
- Only give complete new_body when modifications to title / summary require corresponding adjustments at the beginning of the body.

# Output JSON Format
{
  "should_skip": false,
  "skip_reason": "",
  "new_slot_meta": {
    "id": "original slot_id", "title": "...", "icon": "📄",
    "summary": "...", "aliases": ["..."]
  },
  "new_body": "",
  "self_check": "≤2 lines, brief summary of your judgment process"
}

# Current Inputs

## Reason Given by Planner
{planner_reason}

## Slot (id={slot_id})
title:   {slot_title}
summary: {slot_summary}
icon:    {slot_icon}
aliases: {slot_aliases}
main.md:
{slot_main_md}
"""


def call_curator_execute_edit(
    *,
    slot: dict,
    main_md: str,
    reason_from_planner: str,
    miru_name: str = "Miru",
) -> Optional[EditExecutorOutput]:
    """v3.5 Edit Executor — self-check + execute in one call."""
    miru_name_safe = (miru_name or "Miru").strip() or "Miru"
    user_msg = (
        CURATOR_EXECUTE_EDIT_PROMPT
        .replace("{planner_reason}", reason_from_planner or "")
        .replace("{slot_id}", slot.get("id", "") or "")
        .replace("{slot_title}", slot.get("title", "") or "")
        .replace("{slot_summary}", slot.get("summary", "") or "")
        .replace("{slot_icon}", slot.get("icon", "") or "")
        .replace("{slot_aliases}", str(slot.get("aliases", []) or []))
        .replace("{slot_main_md}", (main_md or "(空)")[:3000])
        .replace("{MIRU_NAME}", miru_name_safe)
    )
    return _call_llm_with_retry(
        messages=[
            {"role": "system", "content": f"You are {miru_name_safe}'s memory curator (edit executor). Output strictly according to the JSON schema."},
            {"role": "user",   "content": user_msg},
        ],
        output_schema=EditExecutorOutput,
        temperature=0.4,
        max_tokens=50000,
        pass_label="CuratorExecuteEdit",
        tier="chat",
        reasoning=False,
        reasoning_budget=0,
    )


# ---------- Delete Executor ----------

class DeleteExecutorOutput(BaseModel):
    """Output of the Delete Executor.

    Delete has no content output — the Executor only decides should_skip
    vs proceed. Caller does the actual move-to-archived if should_skip=false.
    """
    should_skip: bool
    skip_reason: str = ""
    self_check: str = ""

    @field_validator("skip_reason", "self_check")
    @classmethod
    def short_text(cls, v):
        v = (v or "").strip()
        if len(v) > 300:
            v = v[:300]
        return v

    def model_post_init(self, __context):
        if self.should_skip and not self.skip_reason:
            raise ValueError("should_skip=true 时必须给 skip_reason")


CURATOR_EXECUTE_DELETE_PROMPT = """# Who You Are
You are {MIRU_NAME}'s memory curator. {MIRU_NAME} is the user's AI companion, who talks with the user every day and records important matters into slot notes. You do not talk with the user; your job is to respond to slot reorganization operations initiated by the Planner — right now you have received a **delete** operation.

# User Identity (Injected)
The user's name is {USER_NAME}.
{USER_NAME}'s identity ground truth:

{IDENTITY_GROUND_TRUTH}

⚠ Everything described in the identity block above points to the exact same person — {USER_NAME} themselves.
In particular, all aliases listed in the "aliases" field are **each and every one {USER_NAME} themselves**, not someone else.
When you review subject identities in slot bodies, treat all such references as "the user themselves".

# Slot Structure
Each slot is an independent markdown file: id / title / summary / icon / aliases / body.

# Real Purpose of Delete
The purpose of delete is **correction** — not cleaning up outdated content. Outdated content is handled by archiving mechanisms and is not part of delete's responsibilities.

Delete solves two types of issues:
1. **Misplaced classification**: The subject essence of the slot does not match the semantic essence of its domain.
2. **True lack of value**: The slot content is hollow or the result of sleep agent misrecognition.

# Semantic Essence of Domains (Needed for reviewing misplaced classification)
- **person**: The subject is a specific person (or quasi-person) **who is NOT {USER_NAME}**.
  {USER_NAME} themselves (including all aliases listed in identity) do not belong to the person domain — that is the realm of self/identity.
- **self**: The subject is the user's own stable attributes.
- **project**: The subject is something staged that the user is doing.
- **topic**: The subject is repeatedly cared-about events / issues / concepts, not the above three.

# Inputs You Receive
- Current domain
- slot_id
- **Complete main.md** of the slot
- Reason given by the Planner

# Your Job — Reviewing the Planner's Judgment

## Type A — Misplaced Classification
After reading the body:
- Determine which domain the body's subject essence belongs to
- Compare with the current slot's domain
- Inconsistent → Pass Type A

Judging subject essence requires looking at the core of the body content, not superficial keywords.
For example, if a body repeatedly describes a specific person (appearances, relationships, activities, status), even if the slot's current domain is topic, the subject essence is person — which is misplaced.

Special cases (common false-positive defense):
- The "that person" appearing repeatedly in the body has a name/aliases falling into {USER_NAME}'s identity alias set — the subject essence is the user themselves, not a real friend. The user themselves belongs to self/identity, but the slot is in the person domain; this is misplaced classification, pass Type A.
- Do not retain just because the body superficially looks like describing someone — first check if that name is an alias of {USER_NAME}.

## Type B — True Lack of Value
After reading the body:
- Does the body have accumulative, retrievable substantive information?
- Or is it just noise / disposable content / UI residue / notification residue / internally contradictory content?
- If the latter → Pass Type B

## Conditions Where Delete Cannot Be Executed
Even if the Planner's reason seems superficially reasonable, should_skip=true under the following conditions:

1. The body contains uncompleted commitments / things the user is currently doing — delete will lose this information.
2. The Planner's reason essentially talks about "outdatedness" (recently inactive / matter finished / long ago), rather than "misplacement" or "valuelessness". Outdatedness belongs to archiving, not delete.

# Decision
- Passes Type A or Type B, and does not trigger any "cannot execute" conditions
  → should_skip=false, execute delete
- Otherwise → should_skip=true

# Output JSON Format
{
  "should_skip": false,
  "skip_reason": "",
  "self_check": "≤2 lines, briefly state which type you passed or by which rule you were rejected"
}

# Current Inputs

## Current Domain
{domain}

## Reason Given by Planner
{planner_reason}

## Slot (id={slot_id})
title:   {slot_title}
summary: {slot_summary}
icon:    {slot_icon}
aliases: {slot_aliases}
main.md:
{slot_main_md}
"""


def call_curator_execute_delete(
    *,
    domain: str,
    slot: dict,
    main_md: str,
    reason_from_planner: str,
    user_name: str = "",
    identity_ground_truth: str = "",
    miru_name: str = "Miru",
) -> Optional[DeleteExecutorOutput]:
    """v3.5 Delete Executor — self-check before physical archive move.

    user_name / identity_ground_truth: same identity injection as the
    Planner — required so the Executor doesn't keep an alias-misclassified
    person slot by interpreting body's recurring name as "real person".
    """
    miru_name_safe = (miru_name or "Miru").strip() or "Miru"
    user_msg = (
        CURATOR_EXECUTE_DELETE_PROMPT
        .replace("{USER_NAME}", user_name or "用户")
        .replace("{IDENTITY_GROUND_TRUTH}",
                 (identity_ground_truth or "").strip() or "(尚未声明)")
        .replace("{domain}", domain or "")
        .replace("{planner_reason}", reason_from_planner or "")
        .replace("{slot_id}", slot.get("id", "") or "")
        .replace("{slot_title}", slot.get("title", "") or "")
        .replace("{slot_summary}", slot.get("summary", "") or "")
        .replace("{slot_icon}", slot.get("icon", "") or "")
        .replace("{slot_aliases}", str(slot.get("aliases", []) or []))
        .replace("{slot_main_md}", (main_md or "(空)")[:3000])
        .replace("{MIRU_NAME}", miru_name_safe)
    )
    return _call_llm_with_retry(
        messages=[
            {"role": "system", "content": f"You are {miru_name_safe}'s memory curator (delete executor). Output strictly according to the JSON schema."},
            {"role": "user",   "content": user_msg},
        ],
        output_schema=DeleteExecutorOutput,
        temperature=0.2,
        max_tokens=50000,
        pass_label="CuratorExecuteDelete",
        tier="chat",
        reasoning=False,
        reasoning_budget=0,
    )
