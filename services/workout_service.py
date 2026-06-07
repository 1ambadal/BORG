import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from services.db_service import (
    add_workout_entry,
    get_workouts,
    delete_workout_entry,
    add_workout_entries,
    get_unique_exercises,
    ensure_exercise_in_master,
)
from services.llm_service import get_llm
from agent.prompts import WORKOUT_PARSING_PROMPT
from core.models import WorkoutSession
from core.config import settings

logger = logging.getLogger(__name__)


async def process_workout_log(text: str, default_date: Optional[str] = None) -> str:
    """
    Uses LLM with structured output to parse a workout log and save it.
    """
    try:
        master_list = get_unique_exercises()
        master_str = (
            "\n".join([f"- {ex}" for ex in master_list]) if master_list else "None yet."
        )

        llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0.1)
        structured_llm = llm.with_structured_output(WorkoutSession)

        prompt = WORKOUT_PARSING_PROMPT.format(text=text, master_exercises=master_str)
        session = await structured_llm.ainvoke(prompt)

        date = session.date
        if not date or date.lower().strip() in ["null", "none", ""]:
            date = default_date or datetime.now().strftime("%d-%m-%Y")

        entries = []
        for ex in session.exercises:
            entries.append(
                {
                    "exercise": ex.exercise.strip().title(),
                    "sets": ex.sets,
                    "reps": ex.reps,
                    "weight": ex.weight,
                    "date": date,
                }
            )
            ensure_exercise_in_master(ex.exercise)

        count = add_workout_entries(entries)

        return f"Successfully logged {count} exercise(s) on {date}."
    except Exception as e:
        logger.error(f"Error processing workout log: {e}", exc_info=True)
        return f"Failed to parse workout log. Error: {str(e)}"


def log_workout(
    exercise: str,
    sets: int,
    reps: int,
    weight: float,
    date: str = None,
) -> str:
    """
    Logs a workout entry. If date is not provided, uses today's date in DD-MM-YYYY format.
    """
    if not date:
        date = datetime.now().strftime("%d-%m-%Y")

    try:
        entry_id = add_workout_entry(exercise, sets, reps, weight, date)
        return f"Successfully logged {exercise}."
    except Exception as e:
        logger.error(f"Failed to log workout: {e}", exc_info=True)
        return f"Failed to log workout. Error: {str(e)}"


def list_workouts() -> List[Dict[str, Any]]:
    """Returns all logged workouts."""
    return get_workouts()


def remove_workout(entry_id: int) -> str:
    """Removes a workout entry."""
    if delete_workout_entry(entry_id):
        return "Workout entry deleted."
    return "Workout entry not found."
