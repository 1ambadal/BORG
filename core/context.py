from contextvars import ContextVar
from typing import Optional, Any

# Context Variables to store user and chat info safely within async executions
chat_id_var: ContextVar[Optional[int]] = ContextVar("chat_id", default=None)
bot_instance_var: ContextVar[Optional[Any]] = ContextVar("bot_instance", default=None)


def set_context(chat_id: int, bot_instance: Any):
    """Sets the context variables for the current execution flow."""
    chat_token = chat_id_var.set(chat_id)
    bot_token = bot_instance_var.set(bot_instance)
    return chat_token, bot_token


def get_current_chat_id() -> Optional[int]:
    return chat_id_var.get()


def get_current_bot() -> Optional[Any]:
    return bot_instance_var.get()
