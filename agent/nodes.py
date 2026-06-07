"""
This module contains the nodes for the LangGraph agent.
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
from langgraph.prebuilt import ToolNode
from core.config import settings
from core.models import FactList
from services.llm_service import get_llm
from services.db_service import (
    get_recent_messages,
    get_user_facts,
    update_fact_stats,
    save_message,
    add_user_facts,
)
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
from agent.prompts import get_supervisor_system_prompt

logger = logging.getLogger(__name__)

smart_llm = get_llm(temperature=0.3)
fast_llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0.1)
supervisor_llm_base = fast_llm

analyze_missing_skills_node = ToolNode([analyze_missing_skills_tool])
get_company_reviews_node = ToolNode([get_company_reviews_tool])
draft_email_node = ToolNode([draft_email_tool])
final_send_email_node = ToolNode([final_send_email_do_not_call])
get_my_resume_node = ToolNode([list_my_resumes_tool])
reset_user_data_node = ToolNode([reset_user_data_tool])
web_search_node = ToolNode([web_search_tool])
manage_todos_node = ToolNode([manage_todos_tool])
manage_job_applications_node = ToolNode([manage_job_applications_tool])
manage_bookmarks_node = ToolNode([manage_bookmarks_tool])
manage_reminders_node = ToolNode([manage_reminders_tool])
manage_cron_node = ToolNode([manage_cron_tool])
manage_learning_node = ToolNode([manage_learning_tool])
manage_nutrition_node = ToolNode([manage_nutrition_tool])
manage_finance_node = ToolNode([manage_finance_tool])
manage_facts_node = ToolNode([manage_facts_tool])
manage_workouts_node = ToolNode([manage_workouts_tool])
manage_dumps_node = ToolNode([manage_dumps_tool])
manage_calendar_node = ToolNode([manage_calendar_tool])

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

# --- Architecture: In-Memory Cache & Context Builder ---


@dataclass
class BotContext:
    facts: List[str] = field(default_factory=list)
    messages: List[AnyMessage] = field(default_factory=list)
    facts_loaded_at: float = 0
    msgs_loaded_at: float = 0
    persisted_count: int = 0


_cache: Dict[str, BotContext] = {}


def clear_cache(thread_id: str):
    """Clears the in-memory context for a specific thread, and wipes all cache since this is single-user."""
    _cache.clear()


async def ensure_loaded(thread_id: str):
    """Loads history and facts into RAM if missing or expired."""

    if thread_id not in _cache:
        _cache[thread_id] = BotContext()

    ctx = _cache[thread_id]
    now = time.time()

    # 1. Load Messages (Only on first turn / first load)
    if not ctx.messages and ctx.msgs_loaded_at == 0:
        raw_msgs = get_recent_messages(thread_id, limit=20)
        # Convert raw DB rows back to LangChain messages
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

    # 2. Reload Facts if TTL (300s) expired
    if now - ctx.facts_loaded_at > 300:
        facts_raw = get_user_facts()
        ctx.facts = [f["fact_text"] for f in facts_raw]
        ctx.facts_loaded_at = now

        # Trigger background stat updates
        if facts_raw:
            fact_ids = [f["id"] for f in facts_raw]
            asyncio.create_task(async_wrap_stats(fact_ids))


async def async_wrap_stats(fact_ids: List[int]):
    """Helper to run synchronous DB update in background."""

    await asyncio.to_thread(update_fact_stats, fact_ids)


def strip_thought_blocks(msg: AIMessage) -> AIMessage:
    """Return a copy of an AIMessage with thinking blocks removed.

    Gemini 3 thinking models return content as a list that may contain
    {'type': 'thinking', ...} blocks alongside {'type': 'text', ...} blocks.
    These thinking blocks carry a thought_signature that must be replayed
    verbatim - but we don't store it, so we strip them before caching/persisting.
    The resulting message only keeps plain text, which is safe to replay.
    """
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
    """Builds the final message list for the LLM, injecting facts."""
    system_content = base_system_prompt
    if ctx.facts:
        facts_block = "\n".join([f"- {f}" for f in ctx.facts])
        system_content += f"\n\n### [What you know about this user]\n{facts_block}"

    trimmed = list(ctx.messages[-20:])
    while trimmed and not isinstance(trimmed[0], (HumanMessage, SystemMessage)):
        trimmed.pop(0)

    # Collect all tool_call_ids that have matching ToolMessages in the window
    tool_ids = {m.tool_call_id for m in trimmed if isinstance(m, ToolMessage)}

    # Filter orphaned tool_calls AND rebuild messages with empty tool_calls
    cleaned = []
    for m in trimmed:
        if isinstance(m, AIMessage) and m.tool_calls:
            kept = [tc for tc in m.tool_calls if tc.get("id") in tool_ids]
            if kept:
                cleaned.append(AIMessage(content=m.content, tool_calls=kept))
            else:
                # All tool_calls were orphaned — rebuild as plain text message
                cleaned.append(AIMessage(content=m.content or "(used tools)"))
        elif isinstance(m, ToolMessage) and m.tool_call_id not in tool_ids:
            # Orphaned ToolMessage without matching AIMessage tool_call — skip
            continue
        else:
            cleaned.append(m)

    # Final safety: remove any trailing AIMessage with tool_calls that has
    # no following ToolMessages (can happen at conversation boundary)
    while cleaned and isinstance(cleaned[-1], AIMessage) and cleaned[-1].tool_calls:
        cleaned.pop()

    if not cleaned:
        cleaned = [HumanMessage(content="Hello")]

    return [SystemMessage(content=system_content)] + cleaned


async def sync_to_db(
    thread_id: str, new_messages: List[AnyMessage], perform_extraction: bool = True
):
    """Background task to persist messages and extract facts."""

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


def clean_context(messages, window_size=30, output_limit=20):
    if not messages:
        return []

    NOISE_PHRASES = frozenset(
        {
            "hi",
            "hello",
            "yo",
            "ok",
            "okay",
            "thanks",
            "thx",
            "cool",
            "got it",
            "sure",
            "alright",
            "great",
            "noted",
        }
    )

    def is_high_value(m) -> bool:
        """Protect tool calls, system messages, and long content."""
        if isinstance(m, (ToolMessage, SystemMessage)):
            return True
        if isinstance(m, AIMessage) and m.tool_calls:
            return True
        return len(str(m.content).strip()) > 40

    def is_noise(m) -> bool:
        """Only mark human short messages as potential noise."""
        if not isinstance(m, HumanMessage):
            return False  # Never drop AI/Tool/System on noise grounds
        return str(m.content).strip().lower() in NOISE_PHRASES

    # Work within the window
    window = messages[-window_size:]

    # Count noise phrase frequency (human messages only)
    noise_freq: dict[str, int] = {}
    for m in window:
        if is_noise(m):
            key = str(m.content).strip().lower()
            noise_freq[key] = noise_freq.get(key, 0) + 1

    # Track how many times we've seen each noise phrase while iterating
    seen_noise: dict[str, int] = {}
    filtered = []

    for m in window:
        if is_high_value(m):
            filtered.append(m)
            continue

        if is_noise(m):
            key = str(m.content).strip().lower()
            freq = noise_freq.get(key, 1)
            seen_noise[key] = seen_noise.get(key, 0) + 1
            occurrence = seen_noise[key]

            if freq <= 2:
                # Low repetition — keep all
                filtered.append(m)
            elif freq <= 5:
                # Moderate spam — keep first and last only
                is_last = occurrence == freq
                is_first = occurrence == 1
                if is_first or is_last:
                    filtered.append(m)
            else:
                # Heavy spam — keep only the last occurrence
                if occurrence == freq:
                    filtered.append(m)
            continue

        filtered.append(m)

    return filtered[-output_limit:]


async def supervisor_node(state):
    """
    Supervisor refactored with In-Memory Caching & Background Sync.
    """
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

        # Append new ones
        for m in state_msgs[new_start_idx:]:
            ctx.messages.append(m)

    resume_status = "UNKNOWN"
    from services.db_service import get_resume_entry
    from services.user_profile_service import load_user_profile

    resume = get_resume_entry()
    resume_status = "AVAILABLE" if resume else "NOT AVAILABLE"
    profile = load_user_profile() if resume else None

    base_prompt = get_supervisor_system_prompt(resume_status, profile)

    # 4. Build Context-Rich LLM Input
    llm_input = build_llm_context(ctx, base_prompt)

    # 5. Invoke LLM (Upgraded to smart_llm for better reasoning)
    try:
        supervisor_llm = supervisor_llm_base.bind_tools(all_tools)
        result = await supervisor_llm.ainvoke(llm_input)

        # 6. Update RAM with AI response — strip thought blocks so history is
        # always plain text (Gemini rejects replaying raw thinking responses)
        clean_result = strip_thought_blocks(result)
        ctx.messages.append(clean_result)

        # 7. Background Persist of all newly added messages
        new_to_save = ctx.messages[ctx.persisted_count :]
        if new_to_save:
            has_tool_calls = hasattr(result, "tool_calls") and result.tool_calls
            asyncio.create_task(
                sync_to_db(
                    thread_id, list(new_to_save), perform_extraction=not has_tool_calls
                )
            )

        ctx.messages = ctx.messages[-20:]  # Keep RAM lean
        ctx.persisted_count = len(ctx.messages)

        return {"messages": [result]}

    except Exception as e:
        logger.error(f"Supervisor Error: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content="I encountered an error. Please try again.")]
        }
