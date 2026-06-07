"""
tools
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from langchain.tools import tool

from services.company_research import analyze_company_reviews
from services.resume_service import (
    analyze_skill_gap,
    delete_all_resumes,
)
from services.db_service import (
    add_user_facts,
    get_user_facts,
    delete_fact,
    delete_user_custom_data,
    delete_all_checkpoints,
    get_resume_entry,
    add_application_entry,
    get_applications,
    update_application_status,
    delete_application_entry,
    add_bookmark_entry,
    get_user_bookmarks,
    delete_bookmark_entry,
    get_finance_categories,
    add_finance_category,
    delete_finance_category,
    add_finance_transactions,
    get_finance_transactions,
    delete_finance_transaction,
    update_finance_transaction,
    add_food_log,
    get_food_logs_by_date,
    set_user_nutrition_targets,
    get_user_nutrition_targets,
    update_food_log,
    delete_food_log,
)
from services.food_service import parse_food_entry, calculate_user_targets
from services.learning_service import (
    generate_learning_path,
    get_current_lesson,
    complete_current_lesson,
    classify_topic,
)

from services.email_service import send_gmail_message
from services.finance_service import parse_finance_entries
from services.reminder_service import (
    add_reminder,
    get_all_reminders,
    delete_reminder,
    add_recurring_reminder,
    clear_all_reminders,
    scheduler,
)
from services.user_profile_service import delete_all_profile_files
from services.llm_service import get_llm
from services.workout_service import (
    process_workout_log,
    get_workouts,
    delete_workout_entry,
)
from services.dump_service import process_brain_dump
from services.db_service import get_brain_dumps, delete_brain_dump
from core.models import EmailDraft
from core.config import settings
from core.context import get_current_chat_id

logger = logging.getLogger(__name__)


@tool
async def manage_workouts_tool(
    action: str,
    content: Optional[str] = None,
    id: Optional[int] = None,
    date: Optional[str] = None,
) -> str:
    """Workout tracker. action: add|list|delete|categories. 'add' needs content (e.g. 'Bench 100kg 3x5'). 'list' defaults to today (use date=DD-MM-YYYY for history). 'delete' needs id."""
    action = action.lower().strip()

    if action == "add":
        if not content:
            return "Error: content is required to add a workout."

        return await process_workout_log(content)

    elif action == "list":
        target_date = date.strip() if date else datetime.now().strftime("%d-%m-%Y")
        workouts = get_workouts(date=target_date)
        if not workouts:
            return f"No workouts logged on {target_date}."

        summary = f"Workouts for {target_date}:\n"
        for i, w in enumerate(workouts, 1):
            summary += (
                f"{i}. {w['exercise']}: {w['sets']}x{w['reps']} @ {w['weight']}kg\n"
            )
        return summary

    elif action == "delete":
        if not id:
            return "Error: id is required for deletion."

        target_date = date.strip() if date else datetime.now().strftime("%d-%m-%Y")
        workouts_today = get_workouts(date=target_date)

        target_db_id = id
        if 1 <= id <= len(workouts_today):
            target_db_id = workouts_today[id - 1]["id"]

        success = delete_workout_entry(target_db_id)
        return "Workout deleted." if success else "Workout entry not found."

    elif action == "categories":
        from services.db_service import get_unique_exercises

        exercises = get_unique_exercises()
        if not exercises:
            return "No exercises found in history."
        return "Unique Exercises Logged:\n" + "\n".join([f"- {ex}" for ex in exercises])

    return f"Unknown action: {action}"


@tool
async def manage_dumps_tool(
    action: str,
    content: Optional[str] = None,
    id: Optional[int] = None,
) -> str:
    """Brain Dump / personal Knowledge Base for non-actionable items (notes, recipes, ideas). action: add|list|delete. 'add' needs content. 'delete' needs id."""
    if action == "add":
        if not content:
            return "Error: content is required to add a dump."

        res = await process_brain_dump(content)
        if res.get("fallback"):
            return f"Dump saved! Categorized as '{res.get('category')}'."
        return f"Dump saved! Processed {res.get('count', 1)} item(s)."

    elif action == "list":
        dumps = get_brain_dumps()
        if not dumps:
            return "Your Brain Dump is empty."
        output = "Brain Dump Items:\n"
        for i, d in enumerate(dumps[:20], 1):
            tag_str = f" [{', '.join(d['tags'])}]" if d["tags"] else ""
            output += f"{i}. {d['category']}: {d['title']}{tag_str}\n"
        return output

    elif action == "delete":
        if not id:
            return "Error: id is required for deletion."

        dumps = get_brain_dumps()
        target_db_id = id
        if 1 <= id <= len(dumps):
            target_db_id = dumps[id - 1]["id"]

        success = delete_brain_dump(target_db_id)
        return f"Item deleted." if success else f"Item not found."

    return f"Unknown action: {action}"


@tool
async def manage_reminders_tool(
    action: str,
    target_epoch: Optional[float] = None,
    message: Optional[str] = None,
    reminder_id: Optional[str] = None,
) -> str:
    """One-off reminders ONLY (e.g. 'at 5pm'). For recurring use manage_cron_tool. action: add|list|delete|clear_all. 'add' needs message + target_epoch (Unix timestamp). 'delete' needs reminder_id."""
    try:
        chat_id = get_current_chat_id()
        if not chat_id:
            return "Chat context missing."

        action = action.lower().strip()

        if action == "add":
            if not message or not target_epoch:
                return "Both 'message' and 'target_epoch' are required for adding a one-off reminder."

            job_id, result = add_reminder(message.strip(), target_epoch, chat_id)
            if job_id:
                time_str = result.strftime("%d-%m-%Y at %H:%M")
                return f"__REFORMAT__\nReminder set: '{message}' for {time_str}. [ID: {job_id}]"
            return f"Failed to set reminder: {result}"

        elif action == "list":
            reminders = get_all_reminders()
            # Filter for one-off only
            reminders = [r for r in reminders if r["type"] == "one-off"]
            if not reminders:
                return "No pending one-off reminders."
            lines = [
                f"{r['next_run_time'].strftime('%d-%m-%Y %H:%M')} | {r['message']} (ID: {r['id']})"
                for r in reminders
            ]
            return "__REFORMAT__\nPending One-off Reminders:\n\n" + "\n".join(lines)

        elif action == "delete":
            if not reminder_id:
                return "Reminder ID is required."
            if delete_reminder(reminder_id):
                return f"Deleted reminder {reminder_id}."
            return f"Reminder {reminder_id} not found."

        elif action == "clear_all":
            if clear_all_reminders():
                return "All reminders cleared."
            return "Failed to clear reminders."

        return f"Unknown action: {action}. Use 'add', 'list', 'delete', or 'clear_all'."
    except Exception as e:
        logger.error("Error in manage_reminders_tool: %s", e, exc_info=True)
        return f"Error: {str(e)}"


@tool
async def manage_cron_tool(
    action: str,
    message: Optional[str] = None,
    interval_minutes: Optional[int] = None,
    interval_seconds: Optional[int] = None,
    cron_expression: Optional[str] = None,
    reminder_id: Optional[str] = None,
    is_agent_task: bool = False,
) -> str:
    """Recurring tasks/reminders. action: add|list|delete|pause|resume. 'add' needs message + one of: cron_expression (crontab) | interval_minutes | interval_seconds. is_agent_task=True for AI-driven tasks (tool access), False for static text. 'delete/pause/resume' need reminder_id."""
    try:

        chat_id = get_current_chat_id()
        if not chat_id:
            return "Chat context missing."

        action = action.lower().strip()

        if action == "add":
            if not message:
                return "'message' is required for adding a recurring task."
            if not (interval_minutes or interval_seconds or cron_expression):
                return "Must provide a schedule: 'interval_minutes', 'interval_seconds', or 'cron_expression'."

            job_id, schedule = add_recurring_reminder(
                message.strip(),
                interval_minutes,
                interval_seconds,
                cron_expression,
                chat_id,
                is_agent_task=is_agent_task,
            )
            if job_id:
                task_type = "agentic task" if is_agent_task else "recurring reminder"
                return f"__REFORMAT__\nScheduled {task_type}: '{message}' ({schedule}). [ID: {job_id}]"
            return f"Failed to schedule recurring task: {schedule}"

        elif action == "list":
            reminders = get_all_reminders()
            recurring = [r for r in reminders if r["type"] == "recurring"]
            if not recurring:
                return "No recurring tasks found."

            lines = []
            for r in recurring:
                # Determine status
                job = scheduler.get_job(r["id"])
                if job and job.next_run_time is None:
                    status = "Paused"
                else:
                    status = "Active"

                # Determine type
                task_type = "[Agent]" if r.get("is_agent") else "[Static]"

                # Schedule and next run
                sched_info = r.get("schedule", "Unknown schedule")
                next_run = ""
                if r.get("next_run_time"):
                    next_run = (
                        f" | Next: {r['next_run_time'].strftime('%d-%m-%Y %H:%M')}"
                    )

                lines.append(
                    f"- {task_type} {r['message']}: {sched_info} ({status}){next_run} [ID: {r['id']}]"
                )
            return "__REFORMAT__\nRecurring Tasks:\n\n" + "\n".join(lines)

        elif action == "delete":
            if not reminder_id:
                return "Reminder ID is required for 'delete'."
            if delete_reminder(reminder_id):
                return f"Deleted recurring task {reminder_id}."
            return f"Recurring task {reminder_id} not found."

        elif action == "pause":
            if not reminder_id:
                return "Reminder ID is required for 'pause'."
            job = scheduler.get_job(reminder_id)
            if not job:
                return f"Recurring task {reminder_id} not found."
            job.pause()
            return f"Paused recurring task {reminder_id}."

        elif action == "resume":
            if not reminder_id:
                return "Reminder ID is required for 'resume'."
            job = scheduler.get_job(reminder_id)
            if not job:
                return f"Recurring task {reminder_id} not found."
            job.resume()
            return f"Resumed recurring task {reminder_id}."

        return f"Unknown action: {action}. Use 'add', 'list', 'delete', 'pause', or 'resume'."
    except Exception as e:
        logger.error("Error in manage_cron_tool: %s", e, exc_info=True)
        return f"Error: {str(e)}"


@tool
async def get_company_reviews_tool(company_name: str) -> str:
    """Fetch company reputation/culture analysis (Glassdoor/web). Requires company_name."""
    try:
        company_name = company_name.strip()
        if not company_name:
            return "Error: Please provide a company name."

        report = await analyze_company_reviews(company_name)
        if not report or len(report.strip()) < 10:
            return f"I couldn't find any detailed reviews for '{company_name}'. Please verify the name and try again."

        return report
    except Exception as e:
        logger.error(
            "Failed to get company reviews for %s: %s", company_name, e, exc_info=True
        )
        return f"Sorry, I encountered an error while researching reviews for '{company_name}'. Please try again later."


@tool
async def web_search_tool(query: str) -> str:
    """Quick web search for factual lookups (news, emails, stats). Not for full research reports. Requires query string."""
    try:
        query = query.strip()
        if not query:
            return "Error: Please provide a search query."

        from tavily import TavilyClient
        from core.config import settings

        tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
        # Use advanced search depth and more results for better quality
        response = tavily.search(
            query=query, search_depth="advanced", max_results=5, include_answer=True
        )

        results = response.get("results", [])
        answer = response.get("answer")

        if not results and not answer:
            return f"No results found for '{query}'."

        output_parts = []
        if answer:
            output_parts.append(f"Summary\n{answer}\n")

        if results:
            output_parts.append("Search Results")
            for r in results:
                content = r["content"]
                # Truncate content if too long for a quick tool result
                if len(content) > 300:
                    content = content[:300] + "..."
                output_parts.append(f"- [{r['title']}]({r['url']})\n  {content}\n")

        return "__REFORMAT__\n" + "\n".join(output_parts)
    except Exception as e:
        logger.error("Web search failed for query '%s': %s", query, e, exc_info=True)
        return f"Sorry, I encountered an error while searching for '{query}'. Error: {str(e)}"


@tool
def list_my_resumes_tool() -> str:
    """List user's uploaded resume (filename + upload date). Do NOT call this tool when drafting or sending job applications; use draft_email_tool instead. Only call this tool when the user explicitly asks about their resume."""
    try:
        from services.db_service import get_resume_entry

        resume = get_resume_entry()

        if not resume:
            return "I don't have any resumes on file for you. You can upload one using the attachment icon."

        created_at = resume.get("created_at", "Unknown Date")
        file_name = resume.get("file_name", "Unnamed Resume")
        return f"Currently on file:\n1. {file_name} (Uploaded: {created_at})"
    except Exception as e:
        logger.error("Failed to list resumes: %s", e, exc_info=True)
        return f"Error retrieving resume list: {str(e)}"


@tool
async def analyze_missing_skills_tool(job_description: str) -> str:
    """Compare resume against a Job Description and return missing skills. Requires job_description text."""
    try:
        job_description = job_description.strip()
        if not job_description:
            return "Error: Please provide a Job Description to analyze."

        analysis = await analyze_skill_gap(job_description)
        if not analysis:
            return "I couldn't generate a skill gap analysis. Please ensure your resume is uploaded and the JD is clear."

        return "__REFORMAT__\n" + analysis
    except Exception as e:
        logger.error("Skill gap analysis failed: %s", e, exc_info=True)
        return f"Error analyzing skills: {str(e)}"


@tool
async def draft_email_tool(
    recipient_email: str,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    is_job_application: bool = False,
    company_name: Optional[str] = None,
    role_name: Optional[str] = None,
) -> str:
    """Draft an email (Step 1 of 2 — never send directly). Two modes: generic (needs recipient_email+subject+body) or job_application (is_job_application=True + company_name + role_name, auto-generates from resume). Show draft to user and wait for confirmation before calling final_send_email_do_not_call."""
    try:
        if is_job_application:
            if not company_name or not role_name:
                return (
                    "For job applications, 'company_name' and 'role_name' are required."
                )

            from services.db_service import get_resume_entry

            resume_data = get_resume_entry()
            if not resume_data:
                return "I don't have your resume on file. Please upload it first so I can draft this for you!"

            generic_cl = resume_data.get(
                "cover_letter_text", "No baseline cover letter found."
            )

            from agent.prompts import JOB_APPLICATION_EMAIL_PROMPT

            llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0.7)
            structured_llm = llm.with_structured_output(EmailDraft)

            user_instruction = (
                body.strip() if body else "No specific instructions provided."
            )

            prompt = JOB_APPLICATION_EMAIL_PROMPT.format(
                role_name=role_name,
                company_name=company_name,
                generic_cover_letter=generic_cl,
                user_instruction=user_instruction,
            )

            try:
                draft = await structured_llm.ainvoke(prompt)
                final_subject = draft.subject
                final_body = draft.body

            except Exception as e:
                logger.error("Failed to generate structured email draft: %s", e)
                final_subject = f"Application for {role_name} - {company_name}"
                final_body = f"Dear Hiring Manager,\n\nI am interested in the {role_name} position at {company_name}."

        else:
            if not subject or not body:
                return (
                    "For generic emails, 'subject' and 'body' are required parameters."
                )
            final_subject = subject
            final_body = body

        return (
            f"Draft Email Generated:\n"
            f"To: {recipient_email}\n"
            f"Subject: {final_subject}\n\n"
            f"{final_body}\n\n"
            f"--- End of Draft ---\n"
            f"Do you want me to send this email? Please reply with 'Yes' to send, or provide feedback to edit."
        )
    except Exception as e:
        logger.error("Failed to draft email: %s", e, exc_info=True)
        return f"Sorry, I couldn't draft the email. Error: {str(e)}"


@tool
def final_send_email_do_not_call(
    recruiter_email: str,
    subject: str,
    body: str,
    attach_resume: bool = False,
    company_name: Optional[str] = None,
    position: Optional[str] = None,
) -> str:
    """SEND email — ONLY call after explicit user approval of draft. Requires recruiter_email + subject + body. Set attach_resume=True for job applications. Provide company_name+position to auto-save to job tracker."""
    try:
        attachments = []
        if attach_resume:
            resume_data = get_resume_entry()
            resume_path = resume_data.get("file_path") if resume_data else None

            if not resume_path:
                return "No resume found on file to attach. Please upload your resume first."

            attachments = [resume_path]

        result = send_gmail_message(
            to=recruiter_email,
            subject=subject,
            message_body=body,
            attachments=attachments,
        )

        # Auto-save to Job Tracker if company/position provided
        tracker_msg = ""
        if company_name and position:
            try:
                # Check if this application already exists in the tracker
                existing = get_applications()
                match = next(
                    (a for a in existing
                     if a["Company"].strip().lower() == company_name.strip().lower()
                     and a["Position"].strip().lower() == position.strip().lower()),
                    None,
                )

                if match:
                    # Update existing entry: status → Applied, store recruiter email
                    from services.db_service import update_application_entry
                    update_application_entry(
                        app_id=match["id"],
                        status="Applied",
                        email=recruiter_email,
                    )
                    tracker_msg = "\n\nTracker updated: status set to 'Applied'."
                else:
                    # No existing entry — create one with 'Applied' status
                    track_res = add_application_entry(
                        company_name, position, recruiter_email, "Applied"
                    )
                    tracker_msg = f"\n\nAlso: {track_res}"
            except Exception as e:
                logger.error("Failed to auto-track application: %s", e)
                tracker_msg = "\n\n(Note: Email sent, but failed to save to tracker automatically.)"

        return result + tracker_msg

    except Exception as e:
        logger.error(
            "Failed to send email: %s",
            e,
            exc_info=True,
        )
        return f"Failed to send email. Error: {str(e)}"


@tool
def reset_user_data_tool() -> str:
    """PERMANENTLY delete ALL user data (resumes, history, todos, reminders, finance, nutrition, facts). Triggers on: 'reset', 'start fresh', 'wipe'. Execute immediately, confirm after."""
    try:
        # Delete files
        delete_all_resumes()

        # Delete DB records
        delete_user_custom_data()

        # Delete Profile JSON
        from services.user_profile_service import delete_all_profile_files

        delete_all_profile_files()

        # Delete Reminders
        from services.reminder_service import delete_all_reminders
        from agent.nodes import clear_cache
        from services.db_service import delete_checkpoint_data

        delete_all_reminders()

        thread_id = "1"

        # Delete Persisted LangGraph state
        delete_checkpoint_data(thread_id)

        # Clear RAM state
        clear_cache(thread_id)

        logger.info("Data reset")

        return (
            "System Reset Complete.\n\n"
            "I've wiped the slate clean. How can I help you start fresh today?"
        )

    except Exception as e:
        logger.error(
            "Failed to reset user data: %s",
            e,
            exc_info=True,
        )
        return f"I encountered an error while trying to reset your data: {str(e)}"


@tool
def manage_todos_tool(
    action: str,
    task: Optional[str] = None,
    todo_id: Optional[int] = None,
    status: Optional[str] = None,
    date: Optional[str] = None,
    filter_start_date: Optional[str] = None,
    filter_end_date: Optional[str] = None,
) -> str:
    """Actionable TODO list (items with a completable state). action: add|list|complete|delete|update. 'add' needs task (+ optional date DD-MM-YYYY). 'complete/delete/update' need todo_id. Use filter_start_date/filter_end_date for date-range list."""
    try:

        action = action.lower().strip()

        if action == "add":
            if not task or not task.strip():
                return "Task description is required."

            from services.db_service import add_todo_entry

            new_id = add_todo_entry(task.strip(), date=date)

            if new_id:
                res = f"Added: {task}"
                if date:
                    res += f" ({date})"
                else:
                    res += f" ({datetime.now().strftime('%d-%m-%Y')})"
                return res
            return "Failed to add task."

        elif action == "list":
            from services.db_service import get_user_todos

            todos = get_user_todos(filter_start_date, filter_end_date)
            if not todos:
                return "No matching todos found."

            today_date = datetime.now().date()
            yesterday_date = today_date - timedelta(days=1)
            tomorrow_date = today_date + timedelta(days=1)

            output = []
            last_group = None

            for i, t in enumerate(todos, 1):
                icon = "[x]" if t["status"] == "completed" else "[ ]"

                # Dynamic Group Key
                if not t["date"]:
                    group_key = "Other Tasks"
                else:
                    try:
                        d = datetime.strptime(t["date"], "%d-%m-%Y").date()
                        if d == today_date:
                            group_key = "Today"
                        elif d == yesterday_date:
                            group_key = "Yesterday"
                        elif d == tomorrow_date:
                            group_key = "Tomorrow"
                        else:
                            group_key = f"{d.strftime('%d-%m-%Y (%A)')}"
                    except Exception:
                        group_key = t["date"]  # Fallback if string is weird

                if group_key != last_group:
                    output.append(f"\n{group_key}")
                    last_group = group_key

                output.append(f"{i}. {icon} {t['task']}")

            return "\n".join(output).strip()

        elif action in ["complete", "delete", "update"]:
            from services.db_service import (
                update_todo_entry,
                delete_todo_entry,
                get_user_todos,
            )

            target_db_id = todo_id
            if todo_id and 1 <= todo_id <= 100:  # Heuristic for index
                todos = get_user_todos(filter_start_date, filter_end_date)
                if 1 <= todo_id <= len(todos):
                    target_db_id = todos[todo_id - 1]["id"]

            if action == "complete":
                if target_db_id:
                    if update_todo_entry(
                        todo_id=target_db_id, status=status or "completed"
                    ):
                        return "Task marked done."
                    return "Task not found."
                if date:
                    if update_todo_entry(
                        target_date=date, status=status or "completed"
                    ):
                        return (
                            f"All tasks for {date} marked as {status or 'completed'}."
                        )
                    return f"No tasks found for {date}."
                return "Index or Date required."

            elif action == "delete":
                if target_db_id:
                    if delete_todo_entry(todo_id=target_db_id):
                        return "Todo deleted."
                    return "Todo not found."
                elif date:
                    if delete_todo_entry(date=date):
                        return f"All tasks for {date} deleted."
                    return f"No tasks found for {date}."
                return "Index or Date required."

            elif action == "update":
                if not target_db_id:
                    return "Index required."
                if update_todo_entry(
                    todo_id=target_db_id, task=task, status=status, date=date
                ):
                    return "Updated Todo."
                return "Could not update todo."

        else:
            return f"Unknown action: {action}."

    except Exception as e:
        logger.error(
            "Error in manage_todos_tool: %s",
            e,
            exc_info=True,
        )
        return f"Error managing todos: {str(e)}"


@tool
def manage_job_applications_tool(
    action: str,
    company: Optional[str] = None,
    position: Optional[str] = None,
    email: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    url: Optional[str] = None,
    old_company: Optional[str] = None,
    old_position: Optional[str] = None,
    app_id: Optional[int] = None,
) -> str:
    """Job application tracker. action: add|list|update|delete.
    - 'add': needs company + position (status defaults to 'Pending', optional email, notes, url).
    - 'update': needs app_id (or old_company + old_position) and at least one field to update (company, position, status, email, notes, url).
    - 'delete': needs app_id (or company + position).
    - 'list': lists applications.
    status values: Pending|Applied|Interviewing|Offer|Rejected.
    """
    try:
        action = action.lower().strip()
        if action == "add":
            if not company or not position:
                return "Company and Position are required to add an application."

            final_status = status.strip() if status else "Pending"
            add_application_entry(
                company.strip(),
                position.strip(),
                email.strip() if email else None,
                final_status,
                notes,
                url.strip() if url else None,
            )
            
            from services.db_service import get_resume_entry
            resume = get_resume_entry()
            if resume:
                resume_status = "Resume is on file."
            else:
                resume_status = "No resume on file. Please tell the user they can upload their resume using the attachment icon so we can draft tailored applications or do skill gap analysis."
            
            return f"Added to DB. Successfully tracked '{position}' at '{company}'. Status: '{final_status}'. ({resume_status})"

        elif action == "list":
            apps = get_applications(status_filter=status)
            if not apps:
                return f"No applications found{f' with status {status}' if status else ''}."

            lines = []
            for i, app in enumerate(apps, 1):
                line = f"{i}. {app['Company']} - {app['Position']} ({app['Status']})"
                if app.get("Date Applied"):
                    line += f" [Applied: {app['Date Applied']}]"
                if app.get("URL"):
                    line += f" [URL: {app['URL']}]"
                lines.append(line)

            return "Job Applications:\n\n" + "\n".join(lines)

        elif action == "update_status":
            if not company or not position or not status:
                return "Company, Position, and new Status are required to update an application."

            result = update_application_status(
                company.strip(), position.strip(), status.strip()
            )
            return f"{result}"

        elif action == "update":
            target_db_id = app_id
            if app_id and 1 <= app_id <= 100:  # Heuristic for 1-based index from list
                apps = get_applications()
                if 1 <= app_id <= len(apps):
                    target_db_id = apps[app_id - 1]["id"]

            from services.db_service import update_application_entry

            # Attempt update using resolved ID
            success = update_application_entry(
                app_id=target_db_id,
                old_company=old_company,
                old_position=old_position,
                company=company,
                position=position,
                email=email,
                status=status,
                notes=notes,
                url=url,
            )

            # If no index or old_company was passed, but company + position were passed,
            # assume the user wants to find the record by those and update other fields.
            if not success and not target_db_id and not old_company and company and position:
                success = update_application_entry(
                    old_company=company,
                    old_position=position,
                    email=email,
                    status=status,
                    notes=notes,
                    url=url,
                )

            if success:
                return "Application updated successfully."
            return "Application not found or no updates were applied."

        elif action == "delete":
            target_db_id = app_id
            if app_id and 1 <= app_id <= 100:  # Heuristic for 1-based index from list
                apps = get_applications()
                if 1 <= app_id <= len(apps):
                    target_db_id = apps[app_id - 1]["id"]

            if not target_db_id and not (company and position):
                return "Application ID or Company + Position are required to delete an application."

            success = delete_application_entry(
                app_id=target_db_id,
                company=company.strip() if company else None,
                position=position.strip() if position else None,
            )
            if success:
                return "Application deleted."
            return "Application not found."

        else:
            return f"Unknown action: {action}. Use 'add', 'list', 'update', or 'delete'."

    except Exception as e:
        logger.error("Error managing job applications: %s", e, exc_info=True)
        return f"Error updating job tracker: {str(e)}"



@tool
def manage_bookmarks_tool(
    action: str,
    url: Optional[str] = None,
    bookmark_id: Optional[int] = None,
) -> str:
    """Save/manage URL bookmarks. action: add|list|delete. 'add' needs url. 'delete' needs bookmark_id. OUTPUT: plain text lines only — NEVER markdown checklists or '[ ]' format."""
    try:

        action = action.lower().strip()

        if action == "add":
            if not url:
                return "URL is required to add a bookmark."

            bid = add_bookmark_entry(
                url=url.strip(),
            )
            if bid != -1:
                return f"Bookmark saved: {url}"
            return "Failed to save bookmark."

        elif action == "list":
            results = get_user_bookmarks()
            if not results:
                return "Your bookmark list is empty."
            lines = []
            for i, b in enumerate(results, 1):
                info = f"{i}. {b['url']}"
                lines.append(info)
            return "Your bookmarks:\n\n" + "\n".join(lines)

        elif action == "delete":
            if not bookmark_id:
                return "Bookmark index is required for deletion."

            results = get_user_bookmarks()
            target_db_id = bookmark_id
            if 1 <= bookmark_id <= len(results):
                target_db_id = results[bookmark_id - 1]["id"]

            if delete_bookmark_entry(bookmark_id=target_db_id):
                return "Bookmark deleted."
            return "Bookmark not found."

        else:
            return f"Unknown action: {action}. Use 'add', 'list', or 'delete'."

    except Exception as e:
        logger.error("Error in manage_bookmarks_tool: %s", e, exc_info=True)
        return f"Error managing bookmarks: {str(e)}"


@tool
async def manage_learning_tool(
    action: str, topic: Optional[str] = None, sub_topic_id: Optional[int] = None
) -> str:
    """Structured learning paths. action: add|status|complete. 'add' needs topic (creates roadmap, confirm only — do NOT auto-call status). 'complete' marks current sub-topic done and shows next. 'status' shows current lesson."""
    try:

        action = action.lower().strip()

        if action == "add":
            if not topic or not topic.strip():
                return "Topic title is required to start a learning path."

            topic = topic.strip()

            topic_type = await classify_topic(topic)
            success = await generate_learning_path(topic, topic_type)

            if success:
                dashboard_url = f"{settings.WEBHOOK_URL}/app.html"
                return f"Learning path for '{topic}' successfully added. Task complete. \n\n[View on Dashboard]({dashboard_url})"
            return f"Failed to generate a learning path for '{topic}'."

        elif action == "status":
            lesson = get_current_lesson()
            if not lesson:
                return "You don't have an active learning path. Say 'Start a learning path about [Topic]' to begin!"

            return (
                f"Current Lesson: {lesson.get('title', 'Unknown')}\n\n"
                f"To move to the next lesson, say 'Complete lesson'."
            )

        elif action == "complete":
            lesson = get_current_lesson()
            if not lesson:
                return "No active lesson found to complete."

            if complete_current_lesson(lesson["id"]):
                next_lesson = get_current_lesson()
                if next_lesson:
                    return f"Lesson '{lesson['title']}' completed! Your next lesson is '{next_lesson['title']}'. See you tomorrow!"
                return "Congratulations! You've completed the entire learning path for your topic! Want to start something new?"
            return "Failed to update lesson status."

        return f"Unknown action: {action}. Use 'add', 'status', or 'complete'."

    except Exception as e:
        logger.error("Error in manage_learning_tool: %s", e)
        return f"Error managing learning path: {str(e)}"


@tool
def manage_finance_tool(
    action: str,
    expense_text: Optional[str] = None,
    amount: Optional[float] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    category_type: Optional[str] = "expense",
    item_id: Optional[int] = None,
    date: Optional[str] = None,
) -> str:
    """Personal finance tracker. action: add_transaction|list_transactions|edit_transaction|delete_transaction|add_category|list_categories|delete_category.
    - add_transaction: pass expense_text (natural language, e.g. 'uber 200, dosa 50'). Auto-categorizes: Uber=Transport, Netflix=Entertainment, Swiggy=Food. Ambiguous vendors: best guess + tell user.
    - list_transactions: defaults to today; pass date (DD-MM-YYYY) for other dates.
    - edit_transaction/delete_transaction: need item_id.
    - add_category: needs category_name + category_type ('income'|'expense').
    - delete_category: needs item_id or category_name."""
    try:
        action = action.lower().strip()

        if action == "list_categories":
            cats = get_finance_categories()
            if not cats:
                return "No categories found. You can add one using 'add_category'."
            lines = [f"- {c['name']} ({c['type']})" for c in cats]
            return "Finance Categories:\n\n" + "\n".join(lines)

        elif action == "add_category":
            if not category_name:
                return "category_name is required to add a new category."
            category_name = category_name.strip()
            cid = add_finance_category(category_name, category_type)
            if cid != -1:
                return f"Added new {category_type} category: {category_name}"
            return f"Failed to add category '{category_name}'. It may already exist."

        elif action == "delete_category":
            if not item_id and not category_name:
                return "item_id or category_name is required to delete a category."

            target_id = item_id
            target_name = ""

            if not target_id and category_name:
                cats = get_finance_categories()
                target_cat = next(
                    (
                        c
                        for c in cats
                        if c["name"].lower() == category_name.lower().strip()
                    ),
                    None,
                )
                if not target_cat:
                    return f"Category '{category_name}' not found."
                target_id = target_cat["id"]
                target_name = target_cat["name"]

            if delete_finance_category(target_id):
                name_str = f" '{target_name}'" if target_name else ""
                return f"Category{name_str} (ID: {target_id}) and its associated transactions deleted."
            return f"Category {target_id} not found."

        elif action == "add_transaction":
            if not expense_text or not expense_text.strip():
                return "expense_text is required to log transactions (e.g., 'lunch 10, bus 5')."

            cats = get_finance_categories()
            parsed_items = parse_finance_entries(expense_text.strip(), cats)

            if not parsed_items:
                return "Could not parse any transactions from your text. Please try something like 'lunch 10' or 'income 500 salary'."

            details = []
            valid_transactions = []
            total_added = 0

            for item in parsed_items:
                cat_id = item.get("category_id")
                amt = item.get("amount")
                desc = item.get("description", "")

                target_cat = next((c for c in cats if c["id"] == cat_id), None)
                if not target_cat:
                    target_cat = next(
                        (c for c in cats if c["name"].lower() == "general"), None
                    )
                    if target_cat:
                        cat_id = target_cat["id"]
                    else:
                        continue

                valid_transactions.append(
                    {
                        "amount": amt,
                        "category_id": cat_id,
                        "description": desc,
                        "date_logged": date,
                    }
                )

                total_added += amt
                details.append(f"- ${amt:.2f} under '{target_cat['name']}' ({desc})")

            inserted_count = add_finance_transactions(
                valid_transactions, default_date=date
            )

            if inserted_count and inserted_count > 0:
                return (
                    f"Logged {len(details)} transactions (Total: ${total_added:.2f}):\n"
                    + "\n".join(details)
                )
            else:
                return "Failed to save items to the database. Please try again."

        elif action == "list_transactions":
            search_date = date if date else datetime.now().strftime("%d-%m-%Y")
            trans = get_finance_transactions(date=search_date, limit=20)
            if not trans:
                return f"No transactions found for {search_date}."

            output = f"Transactions for {search_date}\n\n"
            output += "| ID | Date | Category | Description | Amount |\n"
            output += "|---|---|---|---|---|\n"

            for t in trans:
                sign = "+" if t["category_type"] == "income" else "-"
                display_date = t["date_logged"]
                output += f"| {t['id']} | {display_date} | {t['category_name']} | {t['description']} | {sign}${t['amount']:.2f} |\n"

            return output.strip()

        elif action == "delete_transaction":
            if not item_id:
                return "item_id is required to delete a transaction."
            if delete_finance_transaction(item_id):
                return f"Deleted transaction {item_id}."
            return f"Transaction {item_id} not found."

        elif action == "edit_transaction":
            if not item_id:
                return "item_id is required to edit a transaction."
            updates = {}
            if amount is not None:
                updates["amount"] = amount
            if description is not None:
                updates["description"] = description
            if category_name is not None:
                cats = get_finance_categories()
                target_cat = next(
                    (
                        c
                        for c in cats
                        if c["name"].lower() == category_name.lower().strip()
                    ),
                    None,
                )
                if not target_cat:
                    cat_list = ", ".join([c["name"] for c in cats])
                    return (
                        f"Category '{category_name}' not found. Available: {cat_list}"
                    )
                updates["category_id"] = target_cat["id"]

            if not updates:
                return "No updates provided for the transaction (provide 'amount', 'description', or 'category_name')."

            if update_finance_transaction(item_id, updates):
                return f"Transaction {item_id} updated successfully."
            return f"Transaction {item_id} not found or update failed."

        else:
            return f"Unknown action: {action}. Available Actions: add_transaction, list_transactions, delete_transaction, edit_transaction, add_category, list_categories."

    except Exception as e:
        logger.error("Error in manage_finance_tool: %s", e, exc_info=True)
        return f"Error managing finances: {str(e)}"


@tool
def manage_nutrition_tool(
    action: str,
    food_text: Optional[str] = None,
    profile_text: Optional[str] = None,
    date: Optional[str] = None,
    log_id: Optional[int] = None,
    food_name: Optional[str] = None,
    name: Optional[str] = None,
    quantity: Optional[str] = None,
    calories: Optional[int] = None,
    protein: Optional[float] = None,
    carbs: Optional[float] = None,
    fat: Optional[float] = None,
) -> str:
    """Nutrition & food log tracker. action: log|set_targets|get_macros|edit|delete.
    - log: needs food_text (natural language, e.g. 'I ate 2 eggs'). Do NOT log ambiguous inputs.
    - set_targets: needs profile_text (age/weight/height/gender/goal).
    - get_macros: daily progress vs targets; pass date (DD-MM-YYYY) or omit for today.
    - edit: needs log_id or food_name; update via name/quantity/calories/protein/carbs/fat fields.
    - delete: needs log_id or food_name."""
    try:

        action = action.lower().strip()

        if action == "log":
            if not food_text or not food_text.strip():
                return "Please provide a description of the food you ate."
            items = parse_food_entry(food_text.strip())
            if not items:
                return "Could not parse any food items. Please be more specific."

            total_cal, total_pro, details = 0, 0.0, []
            for item in items:
                if add_food_log(item, date_logged=date) != -1:
                    cal, pro = item.get("calories", 0), item.get("protein", 0.0)
                    total_cal += cal
                    total_pro += pro
                    details.append(
                        f"- {item.get('quantity', '1 serving')} {item.get('name')} ({cal} Cal, {pro:.1f}g P)"
                    )
            return (
                f"Logged {len(details)} items:\n"
                + "\n".join(details)
                + f"\n\nTotal: {total_cal} Cal | {total_pro:.1f}g P"
            )

        elif action == "set_targets":
            if not profile_text or not profile_text.strip():
                return (
                    "Provide profile details (age, weight, goal) to calculate targets."
                )
            targets = calculate_user_targets(profile_text.strip())
            if not targets or "calories" not in targets:
                return "Could not calculate targets. Check profile details."
            if set_user_nutrition_targets(targets):
                return f"Targets Saved\n{targets.get('calories')} Cal | {targets.get('protein')}g P | {targets.get('carbs')}g C | {targets.get('fat')}g F"
            return "Failed to save targets."

        elif action == "get_macros":
            check_date = date.strip() if date else datetime.now().strftime("%d-%m-%Y")
            display_date = check_date
            logs = get_food_logs_by_date(check_date)
            targets = get_user_nutrition_targets()
            if not logs:
                return f"No food logged on {display_date}. Target: {targets.get('calories', 'N/A')} Cal."

            t_cal = sum(l.get("calories", 0) for l in logs)
            t_pro = sum(l.get("protein", 0.0) for l in logs)
            summary = f"Macros for {display_date}\n\n"
            summary += f"Calories: {t_cal} / {targets.get('calories', 1985)} kcal\n"
            summary += f"{t_pro:.1f}g / {targets.get('protein', '---')}g P\n\nLogs:\n"
            for i, l in enumerate(logs, 1):
                summary += f"{i}. {l.get('quantity', '1 portion')} {l.get('name')} ({l.get('calories')} Cal)\n"
            return summary

        elif action in ["edit", "delete"]:
            target_date = date if date else datetime.now().strftime("%d-%m-%Y")
            logs_today = get_food_logs_by_date(target_date)
            target_id = log_id

            # Resolve ID from name or index if needed
            if target_id and logs_today and 1 <= target_id <= len(logs_today):
                target_id = logs_today[target_id - 1]["id"]
            if not target_id:
                if not logs_today:
                    return "No logs found today to modify."
                if food_name:
                    fn_lower = food_name.lower().strip()
                    matched = [
                        l for l in logs_today if fn_lower in l.get("name", "").lower()
                    ]
                    if not matched:
                        return f"Could not find '{food_name}' in today's logs."
                    target_id = matched[-1]["id"]
                else:
                    target_id = logs_today[-1]["id"]

            if action == "delete":
                if delete_food_log(target_id):
                    return "Log removed."
                return "Failed to delete log."

            updates = {
                k: v
                for k, v in {
                    "name": name.strip() if name else None,
                    "quantity": quantity.strip() if quantity else None,
                    "calories": calories,
                    "protein": protein,
                    "carbs": carbs,
                    "fat": fat,
                }.items()
                if v is not None
            }
            if not updates:
                return "No updates provided."
            if update_food_log(target_id, updates):
                return "Log updated."
            return "Update failed."

        return f"Unknown action: {action}"

    except Exception as e:
        logger.error(f"Nutrition tool error: {e}", exc_info=True)
        return f"Error: {str(e)}"


@tool
def manage_facts_tool(
    action: str,
    fact_text: Optional[str] = None,
    category: Optional[str] = "general",
    fact_id: Optional[int] = None,
    query: Optional[str] = None,
) -> str:
    """Long-term user memory (survives history trimming). action: add|list|delete|search. 'add' needs fact_text + optional category ('preference'|'info'|'work'|'general'). 'delete' needs fact_id. 'search' needs query. Save: preferences, goals, diet needs, skills, locations. No duplicates."""
    try:
        action = action.lower().strip()

        if action == "add":
            if not fact_text or not fact_text.strip():
                return "fact_text is required to remember a new fact."
            fact_text = fact_text.strip()
            category = category.strip() if category else "general"
            success = add_user_facts(fact_text, category)
            if success:
                return f"Fact remembered successfully: '{fact_text}'"
            return "Failed to save the fact. Please try again."

        elif action == "list":
            facts = get_user_facts()
            if not facts:
                return "I don't remember any facts about you yet. Try 'Remember that my birthday is July 10th'."
            lines = [f"{f['id']}. [{f['category']}] {f['fact_text']}" for f in facts]
            return "Remembered Facts:\n\n" + "\n".join(lines)

        elif action == "search":
            if not query or not query.strip():
                return "A search query is required."
            facts = get_user_facts(query.strip())
            if not facts:
                return f"No facts found matching '{query}'."
            lines = [f"{f['id']}. [{f['category']}] {f['fact_text']}" for f in facts]
            return f"Search results for '{query}':\n\n" + "\n".join(lines)

        elif action == "delete":
            if not fact_id:
                return "fact_id is required to delete a fact."
            if delete_fact(fact_id):
                return f"Fact {fact_id} deleted successfully."
            return f"Fact {fact_id} not found."

        else:
            return (
                f"Unknown action: {action}. Use 'add', 'list', 'search', or 'delete'."
            )

    except Exception as e:
        logger.error("Error in manage_facts_tool: %s", e, exc_info=True)
        return f"Error managing facts: {str(e)}"


def format_datetime_friendly(dt_str: str) -> str:
    if not dt_str:
        return ""
    try:
        from datetime import datetime

        if "T" in dt_str:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.strftime("%A, %b %d, %Y at %I:%M %p")
        else:
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
            return dt.strftime("%A, %b %d, %Y (All Day)")
    except Exception:
        return dt_str


@tool
async def manage_calendar_tool(
    action: str,
    summary: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    event_id: Optional[str] = None,
    query: Optional[str] = None,
) -> str:
    """Google Calendar. action: list|create|delete|quick_add. 'list' shows next 30 days (hide IDs from user, keep in memory for delete). 'create' needs summary+start_time+end_time (ISO 8601). 'quick_add' needs query (natural language). 'delete' needs event_id or summary."""
    try:
        from services.calendar_service import (
            list_calendar_events,
            create_calendar_event,
            delete_calendar_event,
            quick_add_event,
        )

        if action == "list":
            events = list_calendar_events()
            if not events:
                return "No upcoming events found in the next 30 days."

            lines = []
            for e in events:
                start_time = e["start"].get("dateTime", e["start"].get("date"))
                lines.append(f"- {start_time}: {e['summary']} [ID: {e['id']}]")

            return "__REFORMAT__\n" + "\n".join(lines)

        elif action == "create":
            if not all([summary, start_time, end_time]):
                return "summary, start_time, and end_time are required for 'create'."
            res = create_calendar_event(
                summary, start_time, end_time, description, location
            )
            if "error" in res:
                return f"Error: {res['error']}"
            start_raw = res.get("start", {}).get(
                "dateTime", res.get("start", {}).get("date")
            )
            friendly_date = format_datetime_friendly(start_raw)
            return f"Event created successfully:\n- {res.get('summary')}\n- Date: {friendly_date}"

        elif action == "quick_add":
            if not query:
                return "query is required for 'quick_add'."
            res = await quick_add_event(query)
            if "error" in res:
                return f"Error: {res['error']}"

            start_raw = res.get("start", {}).get(
                "dateTime", res.get("start", {}).get("date")
            )
            friendly_date = format_datetime_friendly(start_raw)
            return f"Event added successfully:\n- {res.get('summary')}\n- Date: {friendly_date}"

        elif action == "delete":
            if not event_id and summary:
                events = list_calendar_events()
                matching = [
                    e
                    for e in events
                    if e.get("summary", "").strip().lower() == summary.strip().lower()
                ]
                if matching:
                    event_id = matching[0]["id"]
                else:
                    return (
                        f"Error: No upcoming event found matching summary '{summary}'"
                    )

            if not event_id:
                return "event_id or summary is required for 'delete'."
            res = delete_calendar_event(event_id)
            if res.get("success"):
                return f"Event {event_id} deleted successfully."
            return f"Failed to delete event: {res.get('error')}"

        return (
            f"Unknown action: {action}. Use 'list', 'create', 'delete', or 'quick_add'."
        )

    except Exception as e:
        logger.error(f"Error in manage_calendar_tool: {e}")
        return f"Error: {str(e)}"


@tool
async def manage_job_scraper_tool(
    action: str,
    keywords: Optional[List[str]] = None,
    locations: Optional[List[str]] = None,
    mandatory_skill: Optional[str] = None,
    nice_to_have: Optional[List[str]] = None,
    exp_min: Optional[int] = None,
    exp_max: Optional[int] = None,
) -> str:
    """AI job scraper. action: run|status|config|list. 'run' triggers background crawl (optional keywords/locations lists). 'status' checks progress. 'config' views/updates params (keywords, locations, mandatory_skill, nice_to_have, exp_min, exp_max). 'list' shows recent scraped jobs."""
    try:
        import json
        from services.job_scraper_service import (
            trigger_job_scraper,
            state,
            get_scraper_config,
            save_scraper_config,
        )
        from services.db_service import get_scraped_jobs

        action = action.lower().strip()

        if action == "run":
            started = trigger_job_scraper(keywords, locations)
            if started:
                return "Job scraper triggered successfully in the background! Use action='status' to monitor progress."
            else:
                return f"Job scraper is already running: {state.status_message}"

        elif action == "status":
            run_state = "Running" if state.is_running else "Idle"
            status_text = (
                f"Status: {run_state}\n"
                f"Message: {state.status_message or 'N/A'}\n"
                f"Last Run Time: {state.last_run_time or 'Never'}\n"
                f"Scraped Count: {state.scraped_count}\n"
            )
            if state.error_message:
                status_text += f"Error: {state.error_message}\n"
            return status_text

        elif action == "config":
            cfg = get_scraper_config()
            updated = False
            if keywords is not None:
                cfg["keywords"] = keywords
                updated = True
            if locations is not None:
                cfg["locations"] = locations
                updated = True
            if mandatory_skill is not None:
                cfg["mandatory_skill"] = mandatory_skill
                updated = True
            if nice_to_have is not None:
                cfg["nice_to_have"] = nice_to_have
                updated = True
            if exp_min is not None:
                cfg["exp_min"] = exp_min
                updated = True
            if exp_max is not None:
                cfg["exp_max"] = exp_max
                updated = True

            if updated:
                save_scraper_config(cfg)
                return f"Scraper configuration updated successfully:\n{json.dumps(cfg, indent=2)}"

            return f"Current Scraper Configuration:\n{json.dumps(cfg, indent=2)}"

        elif action == "list":
            jobs = get_scraped_jobs()
            if not jobs:
                return "No scraped jobs found in the database."

            lines = []
            for i, j in enumerate(jobs[:20], 1):
                lines.append(
                    f"{i}. {j['title']} at {j['company']} ({j['location']}) - Posted: {j['date_posted']}\n   URL: {j['url']}"
                )

            return "Recently Scraped Jobs:\n\n" + "\n".join(lines)

        else:
            return (
                f"Unknown action: {action}. Use 'run', 'status', 'config', or 'list'."
            )

    except Exception as e:
        logger.error(f"Error in manage_job_scraper_tool: {e}", exc_info=True)
        return f"Error: {str(e)}"


@tool
async def clear_user_data_tool(confirmation: str) -> str:
    """IRREVERSIBLE: Clears ALL user data (resume, todos, bookmarks, reminders, finance, food logs, facts, LangGraph checkpoints). Requires confirmation='YES' to proceed."""
    if confirmation.upper() != "YES":
        return "Error: Confirmation 'YES' required to clear all data."

    try:
        # 1. Clear database tables
        delete_user_custom_data()
        delete_all_checkpoints()

        # 2. Clear resume files
        delete_all_resumes()
        delete_all_profile_files()

        # 3. Clear scheduled reminders/tasks
        clear_all_reminders()

        return "Success: All user data has been cleared. You are starting fresh!"
    except Exception as e:
        logger.error(f"Failed to clear user data: {e}")
        return f"Error: Failed to clear data. Partial data may have been removed. {e}"
