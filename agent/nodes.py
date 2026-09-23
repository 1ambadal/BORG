"""
Nodes and helper utilities for the LangGraph supervisor agent.
"""

import json
import time
import logging
import asyncio
from typing import List, Dict
from dataclasses import dataclass, field

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    AnyMessage,
)
from core.config import settings
from core.models import FactList
from services.llm_service import get_llm
from services.jev_service import jev_summary, JevClassification
from services.db_service import (
    get_recent_messages,
    get_user_facts,
    update_fact_stats,
    save_message,
    add_user_facts,
    get_resume_entry,
)
from services.user_profile_service import load_user_profile
from agent.prompts import get_supervisor_system_prompt
from agent.tools import (
    analyze_missing_skills_tool,
    get_company_reviews_tool,
    draft_email_tool,
    final_send_email_do_not_call,
    list_my_resumes_tool,
    reset_user_data_tool,
    web_search_tool,
    manage_job_applications_tool,
    manage_bookmarks_tool,
    manage_reminders_tool,
    manage_cron_tool,
    manage_learning_tool,
    manage_nutrition_tool,
    manage_finance_tool,
    manage_facts_tool,
    manage_calendar_tool,
    manage_todos_tool,
    manage_workouts_tool,
    manage_dumps_tool,
    manage_job_scraper_tool,
)

logger = logging.getLogger(__name__)

fast_llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0.1)
supervisor_llm_base = fast_llm

all_tools = [
    analyze_missing_skills_tool,
    get_company_reviews_tool,
    draft_email_tool,
    final_send_email_do_not_call,
    list_my_resumes_tool,
    web_search_tool,
    reset_user_data_tool,
    manage_job_applications_tool,
    manage_bookmarks_tool,
    manage_reminders_tool,
    manage_cron_tool,
    manage_learning_tool,
    manage_nutrition_tool,
    manage_finance_tool,
    manage_facts_tool,
    manage_calendar_tool,
    manage_todos_tool,
    manage_workouts_tool,
    manage_dumps_tool,
    manage_job_scraper_tool,
]

# ---------------------------------------------------------------------------
# Tool Bucket Routing Map & Fact Extraction Gates
# ---------------------------------------------------------------------------

BUCKET_CONFIDENCE_THRESHOLD = 0.75

TOOL_BUCKETS: dict[str, list] = {
    "email":     [draft_email_tool, final_send_email_do_not_call],
    "job_hunt":  [
        manage_job_applications_tool, manage_job_scraper_tool,
        analyze_missing_skills_tool, get_company_reviews_tool,
        list_my_resumes_tool, web_search_tool,
    ],
    "calendar":  [manage_calendar_tool, manage_reminders_tool, manage_cron_tool],
    "todos":     [manage_todos_tool],
    "learning":  [manage_learning_tool, web_search_tool],
    "nutrition": [manage_nutrition_tool],
    "finance":   [manage_finance_tool],
    "notes":     [manage_facts_tool, manage_dumps_tool],
    "bookmarks": [manage_bookmarks_tool],
    "workouts":  [manage_workouts_tool],
    "search":    [web_search_tool],
    "admin":     [reset_user_data_tool],
}

_NO_EXTRACT_BUCKETS: frozenset[str] = frozenset({
    "calendar", "todos", "nutrition", "finance",
    "workouts", "notes", "bookmarks", "admin", "reminders",
})


# ---------------------------------------------------------------------------
# In-Memory Cache
# ---------------------------------------------------------------------------

@dataclass
class BotContext:
    facts: List[str] = field(default_factory=list)
    messages: List[AnyMessage] = field(default_factory=list)
    facts_loaded_at: float = 0
    msgs_loaded_at: float = 0
    persisted_count: int = 0


_cache: Dict[str, BotContext] = {}


def clear_cache(thread_id: str):
    """Clears in-memory context."""
    _cache.clear()


async def ensure_loaded(thread_id: str):
    """Loads history and facts into RAM if missing or expired (300s TTL)."""
    if thread_id not in _cache:
        _cache[thread_id] = BotContext()

    ctx = _cache[thread_id]
    now = time.time()

    if not ctx.messages and ctx.msgs_loaded_at == 0:
        raw_msgs = get_recent_messages(thread_id, limit=20)
        lc_msgs = []
        for rm in raw_msgs:
            role = rm["role"]
            content = rm["content"]
            t_calls = json.loads(rm["tool_calls"]) if rm["tool_calls"] else None
            t_call_id = rm["tool_call_id"]

            if role == "human":
                lc_msgs.append(HumanMessage(content=content))
            elif role == "ai":
                lc_msgs.append(AIMessage(content=content, tool_calls=t_calls or []))
            elif role == "tool":
                lc_msgs.append(ToolMessage(content=content, tool_call_id=t_call_id))

        ctx.messages = lc_msgs
        ctx.msgs_loaded_at = now
        ctx.persisted_count = len(lc_msgs)

    if now - ctx.facts_loaded_at > 300:
        facts_raw = get_user_facts()
        ctx.facts = [f["fact_text"] for f in facts_raw]
        ctx.facts_loaded_at = now

        if facts_raw:
            fact_ids = [f["id"] for f in facts_raw]
            asyncio.create_task(async_wrap_stats(fact_ids))


async def async_wrap_stats(fact_ids: List[int]):
    await asyncio.to_thread(update_fact_stats, fact_ids)


def strip_thought_blocks(msg: AIMessage) -> AIMessage:
    """Strips thinking blocks from raw model outputs for safe history replay."""
    content = msg.content
    if isinstance(content, list):
        text_parts = [
            block if isinstance(block, str) else block.get("text", "")
            for block in content
            if isinstance(block, str) or block.get("type") == "text"
        ]
        content = "".join(text_parts)
    return AIMessage(content=content, tool_calls=msg.tool_calls)


def build_llm_context(ctx: BotContext, base_system_prompt: str) -> List[AnyMessage]:
    """Constructs system prompt and active message window for LLM invocation."""
    system_content = base_system_prompt
    if ctx.facts:
        facts_block = "\n".join([f"- {f}" for f in ctx.facts])
        system_content += f"\n\n### [What you know about this user]\n{facts_block}"

    trimmed = list(ctx.messages[-20:])
    while trimmed and not isinstance(trimmed[0], (HumanMessage, SystemMessage)):
        trimmed.pop(0)

    tool_ids = {m.tool_call_id for m in trimmed if isinstance(m, ToolMessage)}

    cleaned = []
    for m in trimmed:
        if isinstance(m, AIMessage) and m.tool_calls:
            kept = [tc for tc in m.tool_calls if tc.get("id") in tool_ids]
            if kept:
                cleaned.append(AIMessage(content=m.content, tool_calls=kept))
            else:
                cleaned.append(AIMessage(content=m.content or "(used tools)"))
        elif isinstance(m, ToolMessage) and m.tool_call_id not in tool_ids:
            continue
        else:
            cleaned.append(m)

    while cleaned and isinstance(cleaned[-1], AIMessage) and cleaned[-1].tool_calls:
        cleaned.pop()

    if not cleaned:
        cleaned = [HumanMessage(content="Hello")]

    return [SystemMessage(content=system_content)] + cleaned


async def sync_to_db(
    thread_id: str, new_messages: List[AnyMessage], perform_extraction: bool = True
):
    """Background task to persist messages and conditionally extract user facts."""
    for m in new_messages:
        role = (
            "human"
            if isinstance(m, HumanMessage)
            else (
                "ai"
                if isinstance(m, AIMessage)
                else "system" if isinstance(m, SystemMessage) else "tool"
            )
        )
        t_calls = (
            json.dumps(m.tool_calls)
            if isinstance(m, AIMessage) and m.tool_calls
            else None
        )
        t_call_id = getattr(m, "tool_call_id", None)
        save_message(thread_id, role, str(m.content), t_calls, t_call_id)

    if perform_extraction and len(new_messages) >= 2:
        extraction_llm = get_llm(
            model=settings.DEFAULT_FAST_MODEL, temperature=0
        ).with_structured_output(FactList)
        recent_text = "\n".join(
            [f"{type(m).__name__}: {m.content}" for m in new_messages[-2:]]
        )
        prompt = f"Extract persistent user facts from this exchange. Return empty list if none.\n\n{recent_text}"
        try:
            result = await extraction_llm.ainvoke(prompt)
            new_facts = result.facts if result else []
            if new_facts:
                add_user_facts(new_facts)
                if thread_id in _cache:
                    _cache[thread_id].facts.extend(new_facts)
                    _cache[thread_id].facts = list(
                        dict.fromkeys(_cache[thread_id].facts)
                    )[:10]
        except Exception as e:
            logger.error(f"Fact Extraction Error: {e}")


# ---------------------------------------------------------------------------
# Supervisor Node
# ---------------------------------------------------------------------------

async def supervisor_node(state: dict) -> dict:
    """Core supervisor node executing Jev-routed tool binding and prompt assembly."""
    thread_id = "1"
    await ensure_loaded(thread_id)
    ctx = _cache[thread_id]

    state_msgs = state.get("messages", [])
    if state_msgs:
        new_start_idx = 0
        if ctx.messages:
            last_cached = ctx.messages[-1]
            for i in range(len(state_msgs) - 1, -1, -1):
                if str(state_msgs[i].content) == str(last_cached.content) and type(
                    state_msgs[i]
                ) == type(last_cached):
                    new_start_idx = i + 1
                    break

        for m in state_msgs[new_start_idx:]:
            ctx.messages.append(m)

    resume = get_resume_entry()
    resume_status = "AVAILABLE" if resume else "NOT AVAILABLE"
    profile = load_user_profile() if resume else None

    jev_bucket = state.get("jev_bucket", "all")
    jev_bucket_conf = state.get("jev_bucket_confidence") or 0.0
    jev_skipped = state.get("jev_skipped", True)

    base_prompt = get_supervisor_system_prompt(
        resume_status,
        profile,
        jev_bucket=jev_bucket,
        jev_bucket_conf=jev_bucket_conf,
    )

    jev_clf = JevClassification(
        bucket=jev_bucket,
        bucket_confidence=jev_bucket_conf,
        skipped=jev_skipped,
    )
    jev_hint = jev_summary(jev_clf)
    if jev_hint:
        base_prompt = f"{base_prompt}\n\n{jev_hint}"

    llm_input = build_llm_context(ctx, base_prompt)

    # Select Jev-routed subset (high confidence) or full tool set (fallback)
    if (
        not jev_skipped
        and jev_bucket in TOOL_BUCKETS
        and jev_bucket_conf >= BUCKET_CONFIDENCE_THRESHOLD
    ):
        tools_to_use = TOOL_BUCKETS[jev_bucket]
        logger.debug(
            "Jev bucket routing: %s (conf=%.2f) — binding %d/%d tools",
            jev_bucket, jev_bucket_conf, len(tools_to_use), len(all_tools),
        )
    else:
        tools_to_use = all_tools

    try:
        supervisor_llm = supervisor_llm_base.bind_tools(tools_to_use)
        result = await supervisor_llm.ainvoke(llm_input)

        clean_result = strip_thought_blocks(result)
        ctx.messages.append(clean_result)

        new_to_save = ctx.messages[ctx.persisted_count:]
        if new_to_save:
            has_tool_calls = hasattr(result, "tool_calls") and bool(result.tool_calls)
            is_crud_bucket = jev_bucket in _NO_EXTRACT_BUCKETS
            has_user_fact_prob = state.get("jev_has_user_fact", 0.0)

            # Jev-gated fact extraction check
            fact_detected = (has_user_fact_prob >= 0.50) if not jev_skipped else True
            should_extract = (not has_tool_calls) and (not is_crud_bucket) and fact_detected

            asyncio.create_task(
                sync_to_db(
                    thread_id, list(new_to_save), perform_extraction=should_extract
                )
            )

        ctx.messages = ctx.messages[-20:]
        ctx.persisted_count = len(ctx.messages)

        return {"messages": [result]}

    except Exception as e:
        logger.error(f"Supervisor Error: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content="I encountered an error. Please try again.")]
        }
