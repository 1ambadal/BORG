import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from services.google_auth_service import get_google_credentials
from services.llm_service import get_llm
from core.config import settings
from core.models import ParsedCalendarEvent
from agent.prompts import CALENDAR_QUICK_ADD_PROMPT

logger = logging.getLogger(__name__)


_calendar_service = None


def get_calendar_service():
    """Load credentials and return the Calendar service."""
    global _calendar_service
    if _calendar_service is None:
        creds = get_google_credentials()
        _calendar_service = build("calendar", "v3", credentials=creds)
    return _calendar_service


def list_calendar_events(max_results: int = 10) -> List[Dict[str, Any]]:
    """Retrieves upcoming events from the primary calendar."""
    try:
        service = get_calendar_service()
        now_dt = datetime.utcnow()
        now = now_dt.isoformat() + "Z"
        # Limit to 30 days in the future to avoid 10 years of birthdays
        future = (now_dt + timedelta(days=30)).isoformat() + "Z"

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                timeMax=future,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        # Explicitly filter out birthday events to keep the list clean
        filtered_events = [e for e in events if e.get("eventType") != "birthday"]
        return filtered_events
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        return []


def create_calendar_event(
    summary: str,
    start_time: str,  # ISO format
    end_time: str,  # ISO format
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new event in the primary calendar."""
    try:
        service = get_calendar_service()
        event = {
            "summary": summary,
            "location": location,
            "description": description,
            "start": {
                "dateTime": start_time,
                "timeZone": "UTC",  # Simplified for now, can be improved
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "UTC",
            },
        }

        event = service.events().insert(calendarId="primary", body=event).execute()
        return event
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return {"error": str(e)}


def delete_calendar_event(event_id: str) -> Dict[str, Any]:
    """Deletes an event from the primary calendar."""
    try:
        service = get_calendar_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"success": True}
    except Exception as e:
        error_msg = str(e)
        if "birthday" in error_msg.lower():
            return {
                "success": False,
                "error": "Birthday events cannot be deleted via the API.",
            }
        logger.error(f"Error deleting calendar event: {e}")
        return {"success": False, "error": error_msg}


async def quick_add_event(text: str) -> Dict[str, Any]:
    """Uses LLM with structured output to parse natural language and insert into primary calendar."""
    try:
        llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0.1)
        structured_llm = llm.with_structured_output(ParsedCalendarEvent)

        # Get local time with timezone offset
        now = datetime.now().astimezone()
        current_time_str = now.isoformat()
        current_weekday = now.strftime("%A")

        prompt = CALENDAR_QUICK_ADD_PROMPT.format(
            text=text,
            current_time=current_time_str,
            current_weekday=current_weekday,
        )
        parsed = await structured_llm.ainvoke(prompt)
        if not parsed:
            raise ValueError("LLM parsing returned empty result")

        logger.info(f"AI Parsed quick-add event: {parsed}")

        # Insert using create_calendar_event
        event = create_calendar_event(
            summary=parsed.summary,
            start_time=parsed.start_time,
            end_time=parsed.end_time,
            description=parsed.description,
            location=parsed.location,
        )
        return event
    except Exception as e:
        logger.error(f"Error in quick_add_event AI parser: {e}")
        # Fallback to standard quickAdd
        try:
            logger.info("Falling back to native Google Calendar quickAdd.")
            service = get_calendar_service()
            # Since service.events().quickAdd is synchronous/blocking, run it or run in thread pool
            event = service.events().quickAdd(calendarId="primary", text=text).execute()
            return event
        except Exception as fallback_err:
            logger.error(f"Fallback quickAdd also failed: {fallback_err}")
            return {"error": str(e)}
