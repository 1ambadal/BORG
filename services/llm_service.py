"""
This module handles the initialization of LLM instances.
"""

import logging
import threading
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_ollama import ChatOllama
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from core.config import settings
from services.db_service import save_llm_usage

logger = logging.getLogger(__name__)


class TokenLogger(BaseCallbackHandler):
    """Lite callback to log and store token usage without blocking."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    def on_llm_end(self, response, **kwargs):
        try:
            m = response.generations[0][0].message
            usage = getattr(m, "usage_metadata", {})
            if not usage:
                return

            threading.Thread(
                target=lambda: save_llm_usage(
                    self.model_name,
                    usage.get("input_tokens", 0),
                    usage.get("output_tokens", 0),
                    usage.get("total_tokens", 0),
                ),
                daemon=True,
            ).start()
        except Exception as e:
            logger.error(f"TokenLogger error: {e}")


_llm_cache = {}


def get_llm(model: Optional[str] = None, temperature: float = 0.3):
    """Centralized factory for LLM instances."""
    selected_model = model or settings.DEFAULT_SMART_MODEL
    cache_key = (selected_model, temperature)

    global _llm_cache
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    if settings.LLM_PROVIDER.lower() == "ollama":
        logger.info(
            "Initializing Ollama LLM: %s (base=%s)",
            selected_model,
            settings.OLLAMA_BASE_URL,
        )
        llm = ChatOllama(
            model=selected_model,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
            num_ctx=8192,
            callbacks=[TokenLogger(selected_model)],
            model_kwargs={"think": False},
        )
    elif settings.LLM_PROVIDER.lower() == "deepseek":
        logger.info("Initializing DeepSeek LLM: %s", selected_model)
        llm = ChatDeepSeek(
            model=selected_model,
            api_key=settings.LLM_API_KEY,
            temperature=temperature,
            callbacks=[TokenLogger(selected_model)],
            extra_body={"thinking": {"type": "disabled"}},
        )
    elif settings.LLM_PROVIDER.lower() in ("openai", "chatgpt"):
        logger.info("Initializing OpenAI LLM: %s", selected_model)
        llm = ChatOpenAI(
            model=selected_model,
            api_key=settings.LLM_API_KEY,
            temperature=temperature,
            callbacks=[TokenLogger(selected_model)],
        )
    else:
        logger.info("Initializing Google LLM: %s", selected_model)
        llm = ChatGoogleGenerativeAI(
            model=selected_model,
            google_api_key=settings.LLM_API_KEY,
            temperature=temperature,
            convert_system_message_to_human=True,
            callbacks=[TokenLogger(selected_model)],
        )

    _llm_cache[cache_key] = llm
    return llm
