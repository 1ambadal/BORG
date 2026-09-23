"""
Jev classification service using TypeSafe AI (System One model).

Provides lightweight Jev questions:
  - bucket (Choice): Routes directly to one tool bucket, chitchat, generation, or 'all'.
  - has_user_fact (Noul): Gates background fact extraction to save ~4,000 tokens per turn.
"""

import logging
from dataclasses import field, dataclass
from typing import Any, Optional

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class JevClassification:
    """
    Lightweight classification result from TypeSafe Jev.
    """
    bucket: str = "all"
    bucket_confidence: float = 0.0
    has_user_fact: float = 0.0
    raw: object = field(default=None, repr=False)
    skipped: bool = True


async def classify_message(
    message: str,
    history_summary: str = "",
) -> JevClassification:
    """
    Classifies an incoming user message into a single routing bucket using TypeSafe Jev.
    Includes a Noul check for user facts to gate background extraction.
    """
    try:
        api_key: Optional[str] = getattr(settings, "TYPESAFE_API_KEY", None)
        if not api_key:
            return JevClassification(skipped=True)

        from langchain_typesafe import Choice, Noul, TypeSafeClassifier

        classifier = TypeSafeClassifier(api_key=api_key)

        state_text = f"Recent conversation context:\n{history_summary}\n\nUser Message:\n{message}" if history_summary else message

        response = classifier.invoke(
            {
                "state": state_text,
                "questions": {
                    "has_user_fact": Noul(
                        instructions=(
                            "Does the user's message explicitly state a new personal fact, preference, diet rule, "
                            "goal, skill, location, or personal detail worth remembering long-term "
                            "(e.g. 'I live in Paris', 'I am allergic to nuts', 'My target salary is 120k')?"
                        )
                    ),
                    "bucket": Choice(
                        instructions="Select the single category that best describes how to fulfill the user's message:",
                        criteria={
                            "chitchat": "Greetings, thanks, small talk, or one-word acknowledgments (e.g. 'hi', 'how are you', 'thanks').",
                            "calendar": "Reminders, scheduling calendar events, or recurring tasks/cron.",
                            "todos": "Adding, listing, updating, or completing todo tasks.",
                            "nutrition": "Logging meals, food items, calories, or tracking macros.",
                            "finance": "Logging expenses, money transactions, or tracking spending.",
                            "workouts": "Logging gym workouts, exercises, sets, reps, or fitness tracking.",
                            "notes": "Saving notes, brain dumps, or personal facts.",
                            "email": "Composing, drafting, or sending emails.",
                            "job_hunt": "Job searching, scraping listings, analyzing skill gaps, or applying to jobs.",
                            "learning": "Creating or tracking learning roadmaps and study plans.",
                            "bookmarks": "Saving or listing bookmark URLs.",
                            "search": "Factual web search or online lookup.",
                            "admin": "Resetting user data or clearing bot settings.",
                            "generation": "General question, explanation, or writing that does NOT require external tools.",
                            "all": "MULTIPLE distinct requests in a single message requiring tools from different categories (e.g. food AND todo AND reminder).",
                        },
                    ),
                },
            }
        )

        bucket_answer = response.choices["bucket"]
        bucket = bucket_answer.choice
        bucket_confidence = bucket_answer.confidence
        has_user_fact_prob = response.nouls["has_user_fact"].noul

        logger.debug(
            "Jev classification — bucket=%s (conf=%.2f), has_user_fact=%.2f",
            bucket,
            bucket_confidence,
            has_user_fact_prob,
        )

        return JevClassification(
            bucket=bucket,
            bucket_confidence=bucket_confidence,
            has_user_fact=has_user_fact_prob,
            raw=response,
            skipped=False,
        )

    except ImportError:
        logger.warning("langchain-typesafe not installed. Jev classification skipped.")
        return JevClassification(skipped=True)
    except Exception as exc:
        logger.warning("Jev classification failed (%s). Continuing without it.", exc)
        return JevClassification(skipped=True)


def jev_summary(clf: JevClassification) -> str:
    """Short summary string for supervisor prompt context."""
    if clf.skipped:
        return ""
    return f"[Jev Routing] bucket={clf.bucket} (conf={clf.bucket_confidence:.2f})"
