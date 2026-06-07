"""
FastAPI routes for the dashboard UI.
"""

import os
import json
import time
import logging
import asyncio
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent.prompts import FACT_EXTRACTION_PROMPT
from agent.agent import get_agent_response
from services.db_service import (
    get_user_todos,
    add_todo_entry,
    update_todo_entry,
    delete_todo_entry,
    get_user_bookmarks,
    add_bookmark_entry,
    delete_bookmark_entry,
    delete_missing_skill,
    upsert_missing_skill,
    get_topics,
    get_sub_topics,
    get_finance_categories,
    add_finance_category,
    delete_finance_category,
    add_finance_transactions,
    get_finance_transactions,
    delete_finance_transaction,
    update_finance_transaction,
    set_user_nutrition_targets,
    get_user_nutrition_targets,
    get_food_logs_by_date,
    delete_food_log,
    update_food_log,
    add_food_log,
    get_resume_entry,
    clear_resume_table,
    get_applications,
    delete_application_entry,
    add_application_entry,
    update_application_entry,
    get_llm_usage_stats,
    add_user_facts,
    get_user_facts,
    add_workout_entry,
    get_workouts,
    delete_workout_entry,
    get_brain_dumps,
    delete_brain_dump,
    get_unique_dump_metadata,
    get_unique_exercises,
    get_scraped_jobs,
    delete_scraped_job,
    clear_all_scraped_jobs,
)
from services.reminder_service import get_all_reminders, delete_reminder, add_reminder
from services.calendar_service import (
    list_calendar_events,
    create_calendar_event,
    delete_calendar_event,
    quick_add_event,
)
from services.learning_service import (
    get_current_lesson,
    complete_current_lesson,
    generate_learning_path,
)
from services.resume_service import analyze_skill_gap, get_missing_skills
from services.finance_service import parse_finance_entries
from services.food_service import parse_food_entry
from services.llm_service import get_llm
from core.config import settings
from core.models import (
    WorkoutCreateRequest,
    BrainDumpCreateRequest,
    ChatRequest,
    TodoCreateRequest,
    TodoStatusUpdate,
    BookmarkCreateRequest,
    UserProfile,
    ReminderCreateRequest,
    AnalyzeSkillsRequest,
    SkillCreateRequest,
    LearningGenerateRequest,
    SkillActionRequest,
    FinanceCategoryCreate,
    FinanceTransactionCreate,
    FinanceTransactionUpdate,
    GenerateTargetsRequest,
    NutritionTargetsUpdate,
    FoodLogUpdate,
    FoodLogCreate,
    CalendarEventCreate,
    QuickAddEvent,
    DescriptionRequest,
    JobApplicationCreate,
    JobApplicationUpdate,
    ScrapeTriggerRequest,
    ScraperConfigUpdate,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Entry point for the dashboard chat UI."""
    start_time = time.time()
    response = await get_agent_response(req.task)
    duration = time.time() - start_time
    logger.info(f"Dashboard chat processed in {duration:.2f}s")
    return {"response": response}


def get_dashboard_user_id() -> int:
    """Resolves the user ID for dashboard context (defaults to setting)."""
    return settings.DASHBOARD_USER_ID or 1


@router.post("/user/describe")
async def api_describe_user(body: DescriptionRequest):
    """Processes user description to extract and store facts."""
    try:
        llm = get_llm(temperature=0)
        prompt = FACT_EXTRACTION_PROMPT.format(description=body.description)

        response = await llm.ainvoke(prompt)
        content = response.content

        # Parse JSON list
        try:
            facts = json.loads(content)
            if not isinstance(facts, list):
                facts = []
        except:
            facts = [f.strip("- ") for f in str(content).split("\n") if f.strip()]

        if facts:
            add_user_facts(facts, category="profile")

        return {"success": True, "facts_extracted": len(facts)}
    except Exception as e:
        logger.error(f"Error extracting facts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/facts")
async def api_get_facts(limit: int = 5):
    """Retrieves top facts for the dashboard."""
    facts = get_user_facts(limit=limit)
    return {"facts": facts}


@router.get("/todos")
async def get_todos():
    """Retrieves all todo tasks."""
    return {"todos": get_user_todos()}


@router.post("/todos")
async def create_todo(body: TodoCreateRequest):
    """Creates a new todo task."""
    task_text = body.task.strip()
    if not task_text:
        raise HTTPException(status_code=400, detail="Task cannot be empty")

    todo_id = add_todo_entry(task=task_text)
    if todo_id == -1:
        raise HTTPException(status_code=500, detail="Failed to create todo")

    return {"success": True, "id": todo_id}


@router.put("/todos/{todo_id}")
async def update_todo(todo_id: int, body: TodoStatusUpdate):
    """Updates the status of a specific todo task."""
    success = update_todo_entry(todo_id=todo_id, status=body.status)
    if not success:
        raise HTTPException(
            status_code=404, detail="Todo not found or could not be updated"
        )
    return {"success": True}


@router.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int):
    """Deletes a specific todo task."""
    success = delete_todo_entry(todo_id=todo_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Todo not found or could not be deleted"
        )
    return {"success": True}


@router.get("/bookmarks")
async def get_bookmarks():
    """Retrieves all bookmarks."""
    return {"bookmarks": get_user_bookmarks()}


@router.post("/bookmarks")
async def create_bookmark(body: BookmarkCreateRequest):
    """Creates a new bookmark entry."""
    url_text = body.url.strip()
    if not url_text:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    bookmark_id = add_bookmark_entry(url=url_text)
    if bookmark_id == -1:
        raise HTTPException(status_code=500, detail="Failed to create bookmark")

    return {"success": True, "id": bookmark_id}


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark(bookmark_id: int):
    """Deletes a specific bookmark entry."""
    success = delete_bookmark_entry(bookmark_id=bookmark_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Bookmark not found or could not be deleted"
        )
    return {"success": True}


@router.get("/resumes")
async def get_resumes():
    """Retrieves unique resume metadata for the user."""
    resume = get_resume_entry()
    resumes = [resume] if resume else []
    for r in resumes:
        r.pop("resume_text", None)
        r.pop("cover_letter_text", None)
    return {"resumes": resumes}


@router.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: int):
    """Deletes the resume entry from the database."""
    # resume_id is ignored since we only have one
    success = clear_resume_table()
    if not success:
        raise HTTPException(
            status_code=404, detail="Resume not found or could not be deleted"
        )
    return {"success": True}


class CoverLetterUpdate(BaseModel):
    cover_letter: str


@router.get("/user/cover-letter")
async def get_cover_letter():
    """Retrieves the current cover letter for the user."""
    resume = get_resume_entry()
    if not resume:
        return {"cover_letter": ""}
    return {"cover_letter": resume.get("cover_letter_text") or ""}


@router.put("/user/cover-letter")
async def put_cover_letter(body: CoverLetterUpdate):
    """Updates the user's cover letter."""
    from services.db_service import update_cover_letter
    success = update_cover_letter(body.cover_letter)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update cover letter")
    return {"success": True}


@router.get("/user/profile")
async def get_user_profile_endpoint():
    """Retrieves the structured user profile."""
    from services.user_profile_service import load_user_profile
    profile = load_user_profile()
    if not profile:
        return {}
    return profile


@router.put("/user/profile")
async def put_user_profile_endpoint(profile: UserProfile):
    """Updates the structured user profile."""
    from services.user_profile_service import save_user_profile
    success = save_user_profile(profile.model_dump())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save user profile")
    return {"success": True}


@router.get("/reminders")
async def get_reminders():
    """Retrieves all active reminders."""
    jobs = get_all_reminders()
    return {"reminders": jobs}


@router.delete("/reminders/{reminder_id}")
async def delete_reminder_api(reminder_id: str):
    """Cancels and deletes a specific reminder."""
    success = delete_reminder(reminder_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Reminder not found or could not be deleted"
        )
    return {"success": True}


@router.post("/reminders")
async def create_reminder(body: ReminderCreateRequest):
    """Creates a new reminder using natural language processing."""
    target_user = get_dashboard_user_id()

    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        message = body.text.strip()
        target_epoch = None

        if body.target_time:
            # Manual override: Direct DT parsing
            try:
                # Expecting DD-MM-YYYY HH:MM
                dt = datetime.strptime(body.target_time, "%d-%m-%Y %H:%M")
                target_epoch = int(dt.timestamp())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid target_time format. Use DD-MM-YYYY HH:MM",
                )
        else:
            # NLP path
            llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0)
            current_time_iso = datetime.now().isoformat()
            current_epoch = int(datetime.now().timestamp())

            prompt = f"""
            Extract the reminder message and calculate the exact target time based on the user's natural language request.
            The current time is {current_time_iso} (Epoch: {current_epoch}).
            
            User request: "{body.text}"
            
            Respond ONLY with a valid JSON object containing:
            - "message": The clean reminder message (string)
            - "target_epoch": The target time as a Unix epoch timestamp (integer)
            
            Do not include markdown blocks, just the raw JSON.
            """
            response = llm.invoke(prompt)
            # Ultra-robust string conversion
            raw_content = response.content
            if isinstance(raw_content, list):
                content_str = "".join(
                    [
                        c.get("text", str(c)) if isinstance(c, dict) else str(c)
                        for c in raw_content
                    ]
                )
            else:
                content_str = str(raw_content)

            logger.info(f"LLM Response Content: {content_str[:100]}...")
            text_resp = content_str.replace("```json", "").replace("```", "").strip()
            data = json.loads(text_resp)
            message = data.get("message", message)
            target_epoch = data.get("target_epoch")

        if not target_epoch:
            raise HTTPException(
                status_code=400, detail="Could not determine target time"
            )

        # Using target_user as chat_id for dashboard context
        job_id, result_time = add_reminder(message, target_epoch, target_user)

        if job_id:
            # We still show the ISO for user readability in the response message
            return {
                "success": True,
                "message": f"Reminder set for {result_time.isoformat()}",
            }
        else:
            raise HTTPException(
                status_code=400, detail=f"Failed to schedule reminder: {result_time}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/current")
async def get_current_learning():
    """Retrieves the current pending lesson."""
    lesson = get_current_lesson()
    return {"lesson": lesson}


@router.get("/learning/topics")
async def get_learning_topics():
    """Retrieves all learning topics and their progress."""
    topics = get_topics()
    return {"topics": topics}


@router.get("/learning/topics/{topic_id}/subtopics")
async def get_topic_subtopics(topic_id: int):
    """Retrieves all subtopics for a specific learning topic."""
    subtopics = get_sub_topics(topic_id)
    return {"subtopics": subtopics}


@router.post("/learning/complete/{sub_topic_id}")
async def complete_lesson_api(sub_topic_id: int):
    """Marks a specific sub-topic as completed."""
    success = complete_current_lesson(sub_topic_id)
    return {"success": success}


@router.post("/learning/generate")
async def generate_learning_path_api(request: LearningGenerateRequest):
    """Triggers generation of a new learning path."""
    from services.learning_service import generate_learning_path, classify_topic

    topic_title = request.topic_title.strip()
    if not topic_title:
        raise HTTPException(status_code=400, detail="Topic title cannot be empty")

    topic_type = request.topic_type
    if not topic_type:
        topic_type = await classify_topic(topic_title)

    success = await generate_learning_path(topic_title, topic_type)

    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to generate learning path. Check logs."
        )

    return {"success": True, "message": f"Learning path for '{topic_title}' generated!"}

    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to generate learning path. Check logs."
        )

    return {"success": True, "message": f"Learning path for '{topic_title}' generated!"}


@router.get("/applications")
async def get_job_applications():
    """Retrieves all job applications from the Google Sheets tracker."""
    try:
        apps = get_applications()
        return {"applications": apps}
    except Exception as e:
        logger.error(f"Failed to get applications for dashboard: {e}")
        return {"applications": [], "error": str(e)}


@router.post("/applications")
async def create_job_application(body: JobApplicationCreate):
    """Creates a new job application."""
    try:
        add_application_entry(
            company=body.company,
            position=body.position,
            email=body.email,
            status=body.status,
            notes=body.notes,
            url=body.url,
        )
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to create job application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/applications/{app_id}")
async def update_job_application(app_id: int, body: JobApplicationUpdate):
    """Updates a job application's details in the database."""
    try:
        success = update_application_entry(
            app_id=app_id,
            company=body.company,
            position=body.position,
            email=body.email,
            status=body.status,
            notes=body.notes,
            url=body.url,
        )
        if not success:
            raise HTTPException(
                status_code=404, detail="Application not found or could not be updated"
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update job application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/applications/{app_id}")
async def delete_job_application(app_id: int):
    """Deletes a job application from the database."""
    success = delete_application_entry(app_id=app_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Application not found or could not be deleted"
        )
    return {"success": True}


@router.post("/analyze-skills")
async def analyze_skills(request: AnalyzeSkillsRequest):
    """Analyzes the gap between a user's resume and a job description."""

    job_desc = request.job_description.strip()
    if not job_desc:
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    try:
        analysis_markdown = await analyze_skill_gap(job_desc)
        return {"analysis": analysis_markdown}
    except Exception as e:
        logger.error(f"Failed to analyze skills via API: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills")
async def get_skills():
    """Retrieves a list of required skills for a user."""
    try:
        skills = get_missing_skills()
        return {"skills": skills}
    except Exception as e:
        logger.error(f"Failed to get skills for dashboard: {e}")
        return {"skills": [], "error": str(e)}


# --- Workouts ---


@router.get("/workouts")
async def get_workouts_endpoint(date: Optional[str] = None):
    """Returns workout entries, optionally filtered by date."""
    try:
        return {"workouts": get_workouts(date=date)}
    except Exception as e:
        logger.error(f"Error fetching workouts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workouts")
async def create_workout_endpoint(req: WorkoutCreateRequest):
    """Creates a new workout entry (supports structured or natural language input)."""
    try:
        if req.text:
            if not req.text.strip():
                raise HTTPException(status_code=400, detail="Workout content cannot be empty")
            from services.workout_service import process_workout_log
            msg = await process_workout_log(req.text, default_date=req.date)
            return {"status": "success", "message": msg}
        else:
            if not req.exercise:
                raise HTTPException(status_code=400, detail="Exercise name is required for structured log")
            date = req.date or datetime.now().strftime("%d-%m-%Y")
            entry_id = add_workout_entry(
                req.exercise,
                req.sets if req.sets is not None else 1,
                req.reps if req.reps is not None else 0,
                req.weight if req.weight is not None else 0.0,
                date
            )
            return {"status": "success", "id": entry_id, "message": f"Successfully logged {req.exercise}."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workouts/master")
async def get_workout_master_list():
    """Retrieves the list of unique exercises."""
    try:
        exercises = get_unique_exercises()
        return {"exercises": exercises}
    except Exception as e:
        logger.error(f"Error fetching workout master: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch workout master list"
        )


@router.delete("/workouts/{entry_id}")
async def delete_workout_endpoint(entry_id: int):
    """Deletes a workout entry."""
    try:
        success = delete_workout_entry(entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="Entry not found")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error deleting workout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Brain Dumps ---


@router.get("/dumps")
async def get_dumps_endpoint(category: Optional[str] = None, tag: Optional[str] = None):
    """Retrieves all brain dumps with optional filtering."""
    try:
        dumps = get_brain_dumps(category=category, tag=tag)
        return {"dumps": dumps}
    except Exception as e:
        logger.error(f"Error fetching dumps: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dumps/metadata")
async def get_dumps_metadata_endpoint():
    """Returns unique categories and tags."""
    try:
        return get_unique_dump_metadata()
    except Exception as e:
        logger.error(f"Error fetching dump metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dumps")
async def create_dump_endpoint(req: BrainDumpCreateRequest):
    """Creates a new brain dump, intelligently processing it."""
    try:
        from services.dump_service import process_brain_dump

        res = await process_brain_dump(req.content)
        return res
    except Exception as e:
        logger.error(f"Error creating dump: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dumps/{dump_id}")
async def delete_dump_endpoint(dump_id: int):
    """Deletes a brain dump."""
    try:
        success = delete_brain_dump(dump_id)
        if not success:
            raise HTTPException(status_code=404, detail="Dump not found")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error deleting dump: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills")
async def create_skill(body: SkillCreateRequest):
    """Adds or increments a skill count for the user."""
    skill_name = body.skill.strip()
    if not skill_name:
        raise HTTPException(status_code=400, detail="Skill cannot be empty")

    success = upsert_missing_skill(skill_name, increment=1)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add skill")
    return {"success": True}


@router.delete("/skills")
async def delete_skill(request: SkillActionRequest):
    """Deletes a skill from the user's missing skills list."""
    success = delete_missing_skill(request.skill)
    if not success:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"success": True}


@router.post("/skills/learn")
async def trigger_skill_learning(request: SkillActionRequest):
    """Triggers a background task to generate a learning path for a skill."""
    asyncio.create_task(generate_learning_path(request.skill))
    return {"success": True}


# --- Calendar Routes ---


@router.get("/calendar/events")
async def api_list_calendar_events(limit: int = 10):
    """Retrieves upcoming calendar events."""
    events = list_calendar_events(limit)
    return {"events": events}


@router.post("/calendar/events")
async def api_create_calendar_event(body: CalendarEventCreate):
    """Creates a new calendar event."""
    event = create_calendar_event(
        body.summary, body.start_time, body.end_time, body.description, body.location
    )
    if "error" in event:
        raise HTTPException(status_code=500, detail=event["error"])
    return {"success": True, "event": event}


@router.post("/calendar/quick-add")
async def api_quick_add_calendar_event(body: QuickAddEvent):
    """Quickly adds a calendar event from natural language."""
    event = await quick_add_event(body.text)
    if "error" in event:
        raise HTTPException(status_code=500, detail=event["error"])
    return {"success": True, "event": event}


@router.get("/llm/stats")
async def api_get_llm_stats():
    """Retrieves aggregate LLM usage stats."""
    return get_llm_usage_stats()


@router.delete("/calendar/events/{event_id}")
async def api_delete_calendar_event(event_id: str):
    """Deletes a calendar event."""
    result = delete_calendar_event(event_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=400, detail=result.get("error", "Failed to delete event")
        )
    return {"success": True}


# --- Finance Routes ---


@router.get("/finance/categories")
async def api_get_finance_categories():
    """Retrieves all finance categories for the user."""
    cats = get_finance_categories()
    return {"categories": cats}


@router.post("/finance/categories")
async def api_create_finance_category(body: FinanceCategoryCreate):
    """Creates a new finance category."""

    category_name = body.name.strip()
    if not category_name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty")

    cid = add_finance_category(category_name, body.type)
    if cid == -1:
        raise HTTPException(
            status_code=400, detail="Failed to add category. It may already exist."
        )
    return {"success": True, "id": cid}


@router.delete("/finance/categories/{category_id}")
async def api_delete_finance_category(category_id: int):
    """Deletes a specific finance category."""
    success = delete_finance_category(category_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Category not found or could not be deleted"
        )
    return {"success": True}


@router.get("/finance/transactions")
async def api_get_finance_transactions(month: Optional[str] = None):
    """Retrieves finance transactions, optionally filtered by month."""
    trans = get_finance_transactions(month=month)
    return {"transactions": trans}


@router.post("/finance/transactions")
async def api_create_finance_transaction(body: FinanceTransactionCreate):
    """Parses and logs one or more finance transactions from natural language."""

    if not body.text.strip():
        raise HTTPException(
            status_code=400, detail="Transaction description cannot be empty"
        )

    try:
        categories = get_finance_categories()
        if not categories:
            raise HTTPException(
                status_code=400,
                detail="Please add at least one finance category first.",
            )

        parsed_items = parse_finance_entries(body.text, categories)
        if not parsed_items:
            raise HTTPException(
                status_code=400,
                detail="Could not understand the transaction description.",
            )

        inserted_count = add_finance_transactions(parsed_items, body.date_logged)

        return {"success": True, "items_added": inserted_count, "items": parsed_items}
    except Exception as e:
        logger.error(f"Error logging finance transaction via API: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/finance/transactions/{transaction_id}")
async def api_delete_finance_transaction(transaction_id: int):
    """Deletes a specific finance transaction."""
    success = delete_finance_transaction(transaction_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Transaction not found or could not be deleted"
        )
    return {"success": True}


@router.put("/finance/transactions/{transaction_id}")
async def api_update_finance_transaction(
    transaction_id: int, body: FinanceTransactionUpdate
):
    """Updates a specific finance transaction."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    success = update_finance_transaction(transaction_id, updates)
    if not success:
        raise HTTPException(
            status_code=404, detail="Transaction not found or could not be updated"
        )
    return {"success": True}


# --- Food Tracker Routes ---


@router.get("/food/targets")
async def api_get_food_targets():
    """Retrieves nutrition targets for the user."""
    targets = get_user_nutrition_targets()
    return {"targets": targets}


@router.post("/food/targets")
async def api_set_food_targets(body: NutritionTargetsUpdate):
    """Sets nutrition targets for the user."""
    success = set_user_nutrition_targets(body.model_dump())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save targets")
    return {"success": True}


@router.post("/food/generate_targets")
async def api_generate_food_targets(body: GenerateTargetsRequest):
    """Generates and sets nutrition targets from natural language."""
    from services.food_service import calculate_user_targets

    targets = calculate_user_targets(body.profile_text)
    if not targets:
        raise HTTPException(
            status_code=400, detail="Failed to calculate targets from profile text."
        )

    success = set_user_nutrition_targets(targets)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save generated targets")
    return {"success": True, "targets": targets}


@router.get("/food/logs")
async def api_get_food_logs(date: Optional[str] = None):
    """Retrieves food logs for a specific date (defaults to today)."""
    check_date = date if date else datetime.now().strftime("%d-%m-%Y")
    logs = get_food_logs_by_date(check_date)
    return {"date": check_date, "logs": logs}


@router.delete("/food/logs/{log_id}")
async def api_delete_food_log(log_id: int):
    """Deletes a specific food log entry."""
    success = delete_food_log(log_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Log not found or could not be deleted"
        )
    return {"success": True}


@router.put("/food/logs/{log_id}")
async def api_update_food_log(log_id: int, body: FoodLogUpdate):
    """Updates a specific food log entry."""

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    success = update_food_log(log_id, updates)
    if not success:
        raise HTTPException(
            status_code=404, detail="Log not found or could not be updated"
        )
    return {"success": True}


@router.post("/food/logs")
async def api_create_food_log(body: FoodLogCreate):
    """Parses and logs one or more food items from natural language."""

    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Food description cannot be empty")

    try:
        parsed_items = parse_food_entry(body.text)
        if not parsed_items:
            raise HTTPException(
                status_code=400, detail="Could not understand the food description."
            )

        added_count = 0
        for item in parsed_items:
            add_food_log(item, date_logged=body.date)
            added_count += 1

        return {"success": True, "items_added": added_count, "items": parsed_items}
    except Exception as e:
        logger.error(f"Error logging food via API: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Scraped Jobs Routes ---


@router.get("/scraped-jobs")
async def api_get_scraped_jobs(
    keyword: Optional[str] = None,
    location: Optional[str] = None,
):
    """Retrieves scraped jobs with optional filters, ordered by ID descending."""
    try:
        jobs = get_scraped_jobs(keyword=keyword, location=location)
        return {"jobs": jobs}
    except Exception as e:
        logger.error(f"Error fetching scraped jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scraped-jobs/scrape")
async def api_trigger_scrape(body: ScrapeTriggerRequest):
    """Triggers the background job scraper."""
    from services.job_scraper_service import trigger_job_scraper

    success = trigger_job_scraper(keywords=body.keywords, locations=body.locations)
    if not success:
        return {"success": False, "message": "Scraper is already running"}
    return {
        "success": True,
        "message": "Scraper triggered successfully in the background.",
    }


@router.post("/scraped-jobs/{job_id}/track")
async def api_track_scraped_job(job_id: int):
    """Moves a scraped job into the job applications tracker, then deletes it from the scraper list."""
    try:
        # 1. Fetch the job (get all so we can find by id regardless of status)
        jobs = get_scraped_jobs(status=None)
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            raise HTTPException(status_code=404, detail="Scraped job not found")

        # 2. Create application entry (status defaults to 'Pending')
        add_application_entry(
            company=job["company"],
            position=job["title"],
            email=None,
            status="Pending",
            notes=f"Via job scraper. Source: {job['url']}",
            url=job["url"],
        )

        # 3. Delete from scraper table — job now lives in tracker
        delete_scraped_job(job_id)

        return {"success": True, "message": f"Now tracking '{job['title']}' at {job['company']}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking scraped job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scraped-jobs/status")
async def api_get_scrape_status():
    """Gets the current status and metrics of the scraper."""
    from services.job_scraper_service import get_state_dict
    return get_state_dict()


@router.get("/scraped-jobs/config")
async def api_get_scraper_config():
    """Gets the active scraper configuration from the database."""
    from services.job_scraper_service import get_scraper_config

    return get_scraper_config()


@router.post("/scraped-jobs/config")
async def api_save_scraper_config(body: ScraperConfigUpdate):
    """Saves (merge-patches) the scraper configuration. Only provided fields are updated."""
    from services.job_scraper_service import get_scraper_config, save_scraper_config

    try:
        cfg = get_scraper_config()
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        cfg.update(updates)
        save_scraper_config(cfg)
        return {"success": True, "message": "Scraper configuration updated.", "config": cfg}
    except Exception as e:
        logger.error(f"Error saving scraper config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/scraped-jobs/config")
async def api_patch_scraper_config(body: ScraperConfigUpdate):
    """Partially updates scraper config (REST-idiomatic alias for POST config)."""
    return await api_save_scraper_config(body)


@router.get("/scraped-jobs/stream-status")
async def api_stream_scraper_status():
    """Server-Sent Events stream of live scraper progress. Closes when scraper finishes."""
    from services.job_scraper_service import get_state_dict, state
    import json

    async def event_generator():
        while True:
            data = json.dumps(get_state_dict())
            yield f"data: {data}\n\n"
            if not state.is_running:
                yield "event: done\ndata: {}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )


@router.delete("/scraped-jobs/{job_id}")
async def api_delete_scraped_job(job_id: int):
    """Deletes a scraped job by ID."""
    success = delete_scraped_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True}


@router.delete("/scraped-jobs")
async def api_clear_scraped_jobs():
    """Clears all scraped jobs from the database."""
    success = clear_all_scraped_jobs()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear scraped jobs")
    return {"success": True}


@router.post("/system/reset")
async def api_system_reset():
    """Permanently deletes all of the user's data and resets the state."""
    try:
        from agent.tools import reset_user_data_tool

        result_message = reset_user_data_tool.invoke({})
        return {"success": True, "message": result_message}
    except Exception as e:
        logger.error(f"Error resetting system data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/google/status")
async def api_google_status():
    """Checks Google authorization and credentials status."""
    from services.google_auth_service import get_auth_status
    return get_auth_status()


@router.post("/google/credentials")
async def api_upload_credentials(file: UploadFile = File(...)):
    """Uploads a Web Application credentials.json file."""
    from services.google_auth_service import save_credentials
    content = await file.read()
    success, error = save_credentials(content)
    if not success:
        raise HTTPException(status_code=400, detail=error)
    return {"success": True, "message": "credentials.json uploaded successfully."}


@router.get("/google/auth")
async def api_google_auth(request: Request):
    """Redirects to Google OAuth consent screen."""
    from fastapi.responses import RedirectResponse
    from services.google_auth_service import get_auth_url
    url, error = get_auth_url(request)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return RedirectResponse(url)


@router.get("/google/callback")
async def api_google_callback(request: Request, code: str, state: str = None):
    """Handles Google OAuth callback and saves token."""
    from fastapi.responses import RedirectResponse
    from services.google_auth_service import exchange_code
    try:
        success, error = exchange_code(request, code)
        if not success:
            raise HTTPException(status_code=400, detail=error)
        return RedirectResponse("/app.html?view=settings", status_code=302)
    except Exception as e:
        logger.error(f"Google auth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google/disconnect")
async def api_google_disconnect():
    """Disconnects Google account by deleting token.json."""
    from services.google_auth_service import disconnect
    if disconnect():
        return {"success": True, "message": "Disconnected Google account."}
    return {"success": False, "message": "No active authorization found."}

