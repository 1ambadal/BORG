from typing import TypedDict, Annotated, List, Optional
import operator
from langchain_core.messages import AnyMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from agent.nodes import supervisor_node, all_tools


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    target_company: Optional[str]
    raw_jd_text: Optional[str]
    skill_gap_analysis: Optional[str]
    company_intel: Optional[str]
    next_node: Optional[str]
    # Jev pre-classification fields
    jev_bucket: Optional[str]
    jev_bucket_confidence: Optional[float]
    jev_has_user_fact: Optional[float]
    jev_skipped: Optional[bool]


unified_tool_node = ToolNode(all_tools)

# Sentinel prefix embedded by tools that genuinely need LLM post-processing.
REFORMAT_SENTINEL = "__REFORMAT__"

# Fast zero-cost chitchat pre-filter in Python
_CHITCHAT_PREFILTER: frozenset[str] = frozenset({
    "hi", "hello", "hey", "yo", "sup", "hiya", "howdy", "heya",
    "hi there", "hello there", "hey there",
    "ok", "okay", "k", "kk", "cool", "got it", "noted", "alright",
    "sure", "sounds good", "makes sense", "understood",
    "thanks", "thx", "thank you", "ty", "cheers", "appreciate it",
    "great", "nice", "awesome", "perfect", "good", "excellent", "amazing",
    "wow", "nice one", "well done",
    "bye", "goodbye", "cya", "see you", "later", "ttyl", "good night",
    "lol", "haha", "hehe", "hmm", "oh", "ah", "uh", "right",
})


# ---------------------------------------------------------------------------
# Jev Pre-classification Node
# ---------------------------------------------------------------------------

async def jev_node(state: AgentState) -> dict:
    """Classifies incoming user messages using TypeSafe Jev before supervisor execution."""
    from services.jev_service import classify_message
    from langchain_core.messages import HumanMessage, AIMessage as _AIMessage

    messages = state.get("messages", [])
    if not messages:
        return {
            "jev_bucket": "all",
            "jev_bucket_confidence": 0.0,
            "jev_has_user_fact": 0.0,
            "jev_skipped": True,
        }

    # Fast pre-filter check
    latest_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    if latest_human:
        raw_text = str(latest_human.content).strip().lower()
        if raw_text in _CHITCHAT_PREFILTER:
            return {
                "jev_bucket": "chitchat",
                "jev_bucket_confidence": 1.0,
                "jev_has_user_fact": 0.0,
                "jev_skipped": False,
            }

    window = messages[-20:]
    turns = []
    for m in window:
        if isinstance(m, HumanMessage):
            turns.append(f"User: {str(m.content).strip()}")
        elif isinstance(m, _AIMessage):
            text = str(m.content).strip()
            if text and not (not text and m.tool_calls):
                turns.append(f"Bot: {text}")

    if not turns:
        return {
            "jev_bucket": "all",
            "jev_bucket_confidence": 0.0,
            "jev_has_user_fact": 0.0,
            "jev_skipped": True,
        }

    latest_text = str(latest_human.content).strip() if latest_human else ""
    state_text = "\n".join(turns)
    clf = await classify_message(latest_text, state_text)

    return {
        "jev_bucket": clf.bucket,
        "jev_bucket_confidence": clf.bucket_confidence,
        "jev_has_user_fact": clf.has_user_fact,
        "jev_skipped": clf.skipped,
    }


# ---------------------------------------------------------------------------
# Chitchat Fast-path Node
# ---------------------------------------------------------------------------

_CHITCHAT_REPLIES = [
    "Hey! 👋",
    "Hi there!",
    "Hello! How can I help?",
    "Hey, what's up?",
    "Hi! What can I do for you?",
]


def chitchat_node(state: AgentState) -> dict:
    """Zero-cost response node for pure greetings and acknowledgments."""
    import random
    from langchain_core.messages import HumanMessage

    messages = state.get("messages", [])
    latest = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    text = str(latest.content).strip().lower() if latest else ""

    if text in {"hi", "hello", "hey", "yo", "sup"}:
        reply = random.choice(_CHITCHAT_REPLIES)
    elif text in {"thanks", "thx", "thank you", "ty"}:
        reply = "You're welcome! 😊"
    elif text in {"ok", "okay", "k", "cool", "got it", "noted", "alright"}:
        reply = "Got it! Let me know if there's anything else."
    elif text in {"great", "nice", "awesome", "perfect"}:
        reply = "Glad to hear it! 🙌"
    elif text in {"bye", "goodbye", "cya", "see you"}:
        reply = "See you! 👋"
    else:
        reply = "What can I help you with? 😊"

    return {"messages": [AIMessage(content=reply)]}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

def jev_router(state: AgentState) -> str:
    """Routes to chitchat if Jev is confident, otherwise supervisor."""
    jev_skipped = state.get("jev_skipped", True)
    if jev_skipped:
        return "supervisor"

    bucket = state.get("jev_bucket", "all")
    confidence = state.get("jev_bucket_confidence", 0.0)

    if bucket == "chitchat" and confidence >= 0.70:
        return "chitchat"

    return "supervisor"


def tool_result_router(state: AgentState) -> str:
    """Routes to supervisor if reformatting requested, otherwise passthrough."""
    messages = state["messages"]
    tool_messages = []
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            tool_messages.append(msg)
        else:
            break

    for tm in tool_messages:
        content = tm.content or ""
        if isinstance(content, str) and content.startswith(REFORMAT_SENTINEL):
            return "supervisor"

    return "passthrough"


def router(state: AgentState) -> str:
    """Routes to tools if tool_calls present, otherwise END."""
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# ---------------------------------------------------------------------------
# Passthrough Node
# ---------------------------------------------------------------------------

def passthrough_node(state: AgentState) -> dict:
    """Formats trailing ToolMessages into a single AIMessage without extra LLM call."""
    messages = state["messages"]
    tool_messages = []
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            tool_messages.append(msg)
        else:
            break

    tool_messages.reverse()
    if not tool_messages:
        return {"messages": []}

    contents = []
    for tm in tool_messages:
        c = tm.content or ""
        if isinstance(c, str):
            if c.startswith(REFORMAT_SENTINEL):
                c = c[len(REFORMAT_SENTINEL):].lstrip("\n")
            c = c.strip()
            if c:
                contents.append(c)

    if not contents:
        return {"messages": []}

    if len(contents) == 1:
        final_content = contents[0]
    else:
        final_content = "✅ Here's what I logged from your message:\n\n" + "\n\n".join(contents)

    return {"messages": [AIMessage(content=final_content)]}


# ---------------------------------------------------------------------------
# Graph Assembly
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)

workflow.add_node("jev", jev_node)
workflow.add_node("chitchat", chitchat_node)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("passthrough", passthrough_node)
workflow.add_node("tools", unified_tool_node)

workflow.add_edge(START, "jev")

workflow.add_conditional_edges(
    "jev",
    jev_router,
    {"supervisor": "supervisor", "chitchat": "chitchat"},
)

workflow.add_edge("chitchat", END)

workflow.add_conditional_edges(
    "supervisor",
    router,
    {"tools": "tools", END: END},
)

workflow.add_conditional_edges(
    "tools",
    tool_result_router,
    {"supervisor": "supervisor", "passthrough": "passthrough"},
)

workflow.add_edge("passthrough", END)

graph = None


def compile_graph(checkpointer):
    global graph
    graph = workflow.compile(checkpointer=checkpointer)
    return graph


def get_compiled_graph():
    global graph
    if graph is None:
        raise RuntimeError("Graph not compiled. Checkpointer missing.")
    return graph
