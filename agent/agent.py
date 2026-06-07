"""
This module handles the invocation of the LangGraph agent.
"""

import logging
from langchain_core.messages import HumanMessage
import agent.graph as graph_module

logger = logging.getLogger(__name__)


async def get_agent_response(user_input: str) -> str:
    """
    Invokes the LangGraph agent for the given user.
    """
    try:
        config = {"configurable": {"thread_id": "1"}}

        inputs = {"messages": [HumanMessage(content=user_input)], "user_id": 1}

        result_state = await graph_module.graph.ainvoke(inputs, config=config)
        messages = result_state.get("messages", [])

        if messages:
            last_msg = messages[-1]
            if last_msg.content:
                final_text = last_msg.content
                if isinstance(final_text, list):
                    final_text = "".join(
                        [
                            part.get("text", "")
                            for part in final_text
                            if isinstance(part, dict) and "text" in part
                        ]
                    )

                if final_text and final_text.strip():
                    return final_text.replace("**", "")
            else:
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    logger.warning(
                        "Graph ended with pending tool calls: %s",
                        last_msg.tool_calls,
                    )

                return "I encountered an internal state error (Empty Response). Please try again."

        return "I completed the task but have no response to show."

    except Exception as e:
        logger.error("Agent Graph Error: %s", e, exc_info=True)
        return f"An error occurred: {str(e)}"
