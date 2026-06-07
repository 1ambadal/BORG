"""
Brain dump processing service for BORG.
"""

import logging
from typing import Dict, Any
from services.llm_service import get_llm
from services.db_service import add_brain_dump, add_brain_dumps
from agent.prompts import DUMP_PARSING_PROMPT
from core.config import settings
from core.models import BrainDumpList

logger = logging.getLogger(__name__)


async def process_brain_dump(text: str) -> Dict[str, Any]:
    """
    Uses LLM with structured output to intelligently categorize and tag a raw 'brain dump'.
    """
    try:
        llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0.1)
        structured_llm = llm.with_structured_output(BrainDumpList)

        prompt = DUMP_PARSING_PROMPT.format(text=text)
        result = await structured_llm.ainvoke(prompt)

        entries = []
        for item in result.items:
            entries.append(
                {
                    "content": item.content,
                    "title": item.title,
                    "category": item.category,
                    "tags": item.tags,
                }
            )

        count = add_brain_dumps(entries)

        return {
            "success": True,
            "count": count,
            "items": [
                {"title": item.title, "category": item.category, "tags": item.tags}
                for item in result.items
            ],
        }
    except Exception as e:
        logger.error("Error processing brain dump: %s", e, exc_info=True)

        dump_id = add_brain_dump(
            content=text, title="Quick Note", category="Note", tags=["quick"]
        )
        return {"success": True, "id": dump_id, "category": "Note", "fallback": True}
