"""
Learning Service
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from services.db_service import (
    add_topic,
    add_sub_topics,
    get_next_pending_sub_topic,
    update_sub_topic_status,
)
from services.user_profile_service import load_user_profile
from services.reminder_service import add_reminder
from services.llm_service import get_llm
from agent.prompts import (
    LEARNING_ROADMAP_PROMPT,
    LEARNING_DAY_DETAIL_PROMPT,
    LEARNING_MICRO_DETAIL_PROMPT,
)
from core.config import settings
from core.models import LearningRoadmap, DayDetail, MicroDayDetail, TopicClassification
from core.context import get_current_chat_id

logger = logging.getLogger(__name__)


async def classify_topic(topic_title: str) -> str:
    """Identifies if a topic is 'main' or 'micro' using LLM."""
    try:
        user_profile = load_user_profile() or {}
        llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0)
        current_role = user_profile.get("current_role", "Professional")
        industry = user_profile.get("industry", "Business/Tech")

        prompt = f"""
        Classify the learning topic '{topic_title}' for a {current_role} in {industry}.

        1. 'main': Broad domains, large technologies, or wide-ranging concepts that require multiple sessions to cover meaningfully.
        2. 'micro': Specific, granular concepts, patterns, or techniques that can be fully understood in a single focused session.

        Respond with ONLY the word 'main' or 'micro'.
        """

        structured_llm = llm.with_structured_output(TopicClassification)
        result = await structured_llm.ainvoke(prompt)
        topic_type = (result.topic_type if result else "main").lower().strip()
        return topic_type if topic_type in ["main", "micro"] else "main"
    except Exception as e:
        logger.error("Topic Classification Error: %s", e)
        return "main"


async def generate_learning_path(topic_title: str, topic_type: str = "main") -> bool:
    """Entry point for generating learning tracks."""
    try:
        user_profile = load_user_profile() or {}
        if topic_type == "micro":
            return await _generate_micro_path(topic_title, user_profile)
        else:
            return await _generate_main_path(topic_title, user_profile)

    except Exception as e:
        logger.error(
            "Error in learning path generation for '%s': %s",
            topic_title,
            e,
            exc_info=True,
        )
        return False


async def _generate_micro_path(topic_title: str, user_profile: dict) -> bool:
    """Handles single-day micro-learning generation."""

    llm = get_llm(temperature=0.7)

    logger.info(
        "🧩 Micro Track: Designing single-day deep dive for '%s'...", topic_title
    )

    day_llm = llm.with_structured_output(MicroDayDetail)
    st = None
    prompt = LEARNING_MICRO_DETAIL_PROMPT.format(
        title=topic_title,
        current_role=user_profile.get("current_role", "Professional"),
        level=user_profile.get("experience_level", "senior"),
        industry=user_profile.get("industry", "Business/Tech"),
    )

    try:
        details = await day_llm.ainvoke(prompt)
        if details:
            st = {
                "title": topic_title,
                "content_summary": details.the_basics.simple_def,
                "examples": details.real_scenarios,
                "questions": [
                    {
                        "q": q.q,
                        "a": {
                            "red_flag": q.a.red_flag,
                            "pro_answer": q.a.pro_answer,
                            "why": q.a.why,
                        },
                    }
                    for q in details.practice_questions
                ],
                "metadata": {
                    "technical_reality": details.the_basics.technical_reality,
                    "the_truth": details.the_truth.dict(),
                    "the_interview_edge": details.the_interview_edge.dict(),
                },
            }
    except Exception as e:
        logger.error("Failed to generate micro details: %s", e)
        return False

    if not st:
        return False

    # Storage
    topic_id = add_topic(topic_title, "micro")
    if topic_id == -1:
        return False

    if add_sub_topics(topic_id, [st]):
        return True
    return False


async def _generate_main_path(topic_title: str, user_profile: dict) -> bool:
    """Handles standard 5-day learning path generation."""

    llm = get_llm(temperature=0.7)
    curriculum = []

    logger.info("🛣️ Stage 1: Designing roadmap for '%s'...", topic_title)
    roadmap_llm = llm.with_structured_output(LearningRoadmap)
    final_roadmap_prompt = LEARNING_ROADMAP_PROMPT.format(
        topic_title=topic_title,
        current_role=user_profile.get("current_role", "Professional"),
        experience_years=user_profile.get("experience_years", 0),
        level=user_profile.get("experience_level", "senior"),
        industry=user_profile.get("industry", "Tech"),
    )

    roadmap = await roadmap_llm.ainvoke(final_roadmap_prompt)
    titles = (
        [c.component for c in roadmap.roadmap] if roadmap and roadmap.roadmap else []
    )

    if not titles or len(titles) < 3:
        logger.error("Invalid roadmap generated: %s", titles)
        return False

    # Stage 2: Detail Gen (Skipped Research Stage)

    day_llm = llm.with_structured_output(DayDetail)

    for i, comp in enumerate(roadmap.roadmap):
        logger.info("   → Generating Part %s: %s", i + 1, comp.component)

        prompt = LEARNING_DAY_DETAIL_PROMPT.format(
            main_topic=topic_title,
            title=comp.component,
            day_num=i + 1,
            total_days=len(roadmap.roadmap),
            current_role=user_profile.get("current_role", "Professional"),
            level=user_profile.get("experience_level", "senior"),
        )

        try:
            details = await day_llm.ainvoke(prompt)
            if details:
                curriculum.append(
                    {
                        "title": comp.component,
                        "content_summary": details.the_mental_model.definition,
                        "examples": [details.the_implementation.example],
                        "questions": [
                            {
                                "q": st.problem,
                                "a": {
                                    "red_flag": "Incomplete logic",
                                    "pro_answer": st.diagnosis,
                                    "why": "System Flow Diagnosis",
                                },
                            }
                            for st in details.logic_stress_test
                        ]
                        + [
                            {
                                "q": q.question,
                                "a": {
                                    "red_flag": "Incorrect choice",
                                    "pro_answer": q.correct_answer,
                                    "why": f"Options: {', '.join(q.options)}",
                                },
                            }
                            for q in details.the_knowledge_check
                        ],
                        "metadata": {
                            "objective": comp.objective,
                            "mental_model": details.the_mental_model.dict(),
                            "system_flow": details.the_system_flow.dict(),
                            "pro_reality": details.the_pro_reality.dict(),
                            "implementation": details.the_implementation.dict(),
                            "knowledge_check": [
                                q.dict() for q in details.the_knowledge_check
                            ],
                        },
                    }
                )
        except Exception as e:
            logger.error("Failed to generate part %s details: %s", i + 1, e)
            curriculum.append(
                {
                    "title": comp.component,
                    "content_summary": "Details unavailable.",
                    "examples": [],
                    "questions": [],
                    "metadata": {"objective": comp.objective},
                }
            )

    # Stage 4: Storage
    topic_id = add_topic(topic_title, "main")
    if topic_id != -1 and add_sub_topics(topic_id, curriculum):

        chat_id = get_current_chat_id() or 0
        for i, st in enumerate(curriculum):
            remind_at = (
                (datetime.now() + timedelta(days=i + 1))
                .replace(hour=8, minute=0, second=0)
                .timestamp()
            )
            msg = f"🎓 **Day {i+1} Lesson: {st['title']}**\n\n🔗 **[Open Dashboard]({settings.WEBHOOK_URL}/app.html)**"
            add_reminder(chat_id, msg, remind_at)
        return True
    return False


def get_current_lesson() -> Dict[str, Any]:
    """Retrieves the next pending sub-topic."""
    return get_next_pending_sub_topic()


def complete_current_lesson(sub_topic_id: int) -> bool:
    """Marks the current lesson as completed."""
    return update_sub_topic_status(sub_topic_id, "completed")
