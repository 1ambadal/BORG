import logging
import json
from typing import List, Dict, Any
from core.config import settings
from services.llm_service import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from agent.prompts import (
    FOOD_SYSTEM_PROMPT,
    FOOD_PARSING_PROMPT,
    NUTRITION_TARGET_SYSTEM_PROMPT,
    NUTRITION_TARGET_PROMPT,
)

logger = logging.getLogger(__name__)


def _get_llm():
    """Lazy LLM initialization to save RAM."""
    return get_llm(temperature=0)


def parse_food_entry(text: str) -> List[Dict[str, Any]]:
    """
    Parses a natural language food entry and returns nutritional information using Gemini.
    """
    try:
        from core.models import FoodLog

        llm = _get_llm()
        structured_llm = llm.with_structured_output(FoodLog)

        messages = [
            SystemMessage(content=FOOD_SYSTEM_PROMPT),
            HumanMessage(content=FOOD_PARSING_PROMPT.format(text=text)),
        ]

        result = structured_llm.invoke(messages)
        return [item.dict() for item in result.items] if result else []
    except Exception as e:
        logger.error(f"Error parsing food entry: {e}", exc_info=True)
        return []


def calculate_user_targets(profile_text: str) -> Dict[str, Any]:
    """
    Calculates daily calorie and macro targets based on user profile using Gemini.
    """
    try:
        from core.models import NutritionTargets

        llm = _get_llm()
        structured_llm = llm.with_structured_output(NutritionTargets)

        messages = [
            SystemMessage(content=NUTRITION_TARGET_SYSTEM_PROMPT),
            HumanMessage(
                content=NUTRITION_TARGET_PROMPT.format(profile_text=profile_text)
            ),
        ]

        result = structured_llm.invoke(messages)
        return result.dict() if result else {}
    except Exception as e:
        logger.error(f"Error calculating targets: {e}", exc_info=True)
        return {}
