"""
Finance service for managing finance transactions.
"""

import logging
import json
from typing import List, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from core.config import settings
from core.models import TransactionList
from services.llm_service import get_llm
from agent.prompts import FINANCE_SYSTEM_PROMPT, FINANCE_PARSING_PROMPT

logger = logging.getLogger(__name__)


def parse_finance_entries(
    text: str, categories: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Parses a natural language finance entry and matches items to existing user categories.
    """
    cat_context = json.dumps([{"id": c["id"], "name": c["name"]} for c in categories])

    try:

        llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0)
        structured_llm = llm.with_structured_output(TransactionList)

        messages = [
            SystemMessage(content=FINANCE_SYSTEM_PROMPT),
            HumanMessage(
                content=FINANCE_PARSING_PROMPT.format(
                    cat_context=cat_context, text=text
                )
            ),
        ]

        result = structured_llm.invoke(messages)
        return [t.dict() for t in result.transactions] if result else []
    except Exception as e:
        logger.error("Error parsing finance entry: %s", e, exc_info=True)
        return []
