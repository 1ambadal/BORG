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


unified_tool_node = ToolNode(all_tools)

# Sentinel prefix embedded by tools that genuinely need LLM post-processing.
# All other tool outputs go straight to passthrough (no second LLM call).
REFORMAT_SENTINEL = "__REFORMAT__"


# --- Tool Result Router ---
def tool_result_router(state: AgentState):
    """
    After the unified tool node executes, decide whether to go back to
    supervisor (second LLM call) or straight to passthrough.

    - Multiple tool results → supervisor (synthesize unified response)
    - Single tool result with REFORMAT_SENTINEL → supervisor
    - Otherwise → passthrough (tool result is already user-friendly, 0 extra tokens)
    """
    messages = state["messages"]

    # Collect all trailing ToolMessages
    tool_messages = []
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            tool_messages.append(msg)
        else:
            break

    # Multiple tools were called → always synthesize
    if len(tool_messages) > 1:
        return "supervisor"

    # Single tool — only reformat if tool explicitly requested it
    if tool_messages:
        content = tool_messages[0].content or ""
        if isinstance(content, str) and content.startswith(REFORMAT_SENTINEL):
            return "supervisor"
        return "passthrough"

    return "supervisor"


def passthrough_node(state: AgentState):
    """
    Converts the last ToolMessage into an AIMessage so the graph can end cleanly.
    Strips REFORMAT_SENTINEL prefix if present (shouldn't reach here with it, but defensive).
    """
    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, ToolMessage):
        content = last_message.content
        if isinstance(content, str):
            # Strip sentinel just in case
            if content.startswith(REFORMAT_SENTINEL):
                content = content[len(REFORMAT_SENTINEL):].lstrip("\n")
            return {"messages": [AIMessage(content=content)]}
        return {"messages": [AIMessage(content=str(content))]}

    return {"messages": []}


def router(state: AgentState):
    """
    Routes the graph based on the last message from the Supervisor.
    If the Supervisor called one or more tools, route to the unified tool node.
    Otherwise, end.
    """
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END


workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("passthrough", passthrough_node)
workflow.add_node("tools", unified_tool_node)

workflow.add_edge(START, "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    router,
    {
        "tools": "tools",
        END: END,
    },
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
