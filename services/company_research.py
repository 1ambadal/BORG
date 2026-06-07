"""
This module is responsible for researching companies and providing analysis of their reputation.
"""

import logging
import asyncio
from typing import Optional
from tavily import TavilyClient
from core.config import settings
from services.llm_service import get_llm
from agent.prompts import COMPANY_REVIEW_PROMPT

logger = logging.getLogger(__name__)


async def analyze_company_reviews(company_name: str) -> Optional[str]:
    """
    Researches a company's reputation by finding reviews on Glassdoor, AmbitionBox, and Google.
    Provides an analysis of pros, cons, work-life balance, and culture.
    """
    try:
        tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
        query = f"{company_name} company reviews glassdoor ambitionbox google"

        response = await asyncio.to_thread(
            tavily.search, query=query, search_depth="advanced", max_results=8
        )

        results = response.get("results", [])
        if not results:
            return None

        context = "\n\n---\n\n".join(
            f"TITLE: {r.get('title')}\nURL: {r.get('url')}\nCONTENT: {r.get('content')}"
            for r in results
        )

        prompt = COMPANY_REVIEW_PROMPT.format(
            company_name=company_name, context=context
        )

        res = await get_llm(temperature=0.3).ainvoke([("human", prompt)])
        return res.content.replace("**", "").strip()

    except Exception as e:
        logger.error(
            "Failed to analyze company reviews for %s: %s",
            company_name,
            e,
            exc_info=True,
        )
        return None
