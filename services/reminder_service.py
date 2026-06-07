"""
Reminder service for managing reminders and recurring tasks.
"""

import logging
import asyncio
from typing import Any
from datetime import datetime
import uuid
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from core.config import settings

logger = logging.getLogger(__name__)

scheduler = None

# Timeout for agentic cron jobs (prevents hanging if LLM is unresponsive)
AGENT_CRON_TIMEOUT_SECONDS = 120


def init_scheduler(bot_instance):
    """Initializes the APScheduler with a persistent PostgreSQL job store."""
    global scheduler

    jobstores = {"default": SQLAlchemyJobStore(url=settings.DATABASE_URL)}

    scheduler = AsyncIOScheduler(jobstores=jobstores)
    scheduler.start()

    # Store the bot instance on the scheduler so jobs can access it
    scheduler.bot = bot_instance
    logger.info("APScheduler started with persistent store at %s", settings.DATABASE_URL.split("@")[-1])


async def send_reminder_job(chat_id: int, message: str):
    """The function executed by the scheduler when a reminder is due."""
    try:
        if scheduler and hasattr(scheduler, "bot"):
            text = f"⏰ Reminder: {message}"

            await scheduler.bot.send_message(
                chat_id=chat_id, text=text, parse_mode="Markdown"
            )
            logger.info("Reminder sent to chat %s", chat_id)
        else:
            logger.error("Scheduler or bot instance not initialized for reminder job.")
    except Exception as e:
        logger.error("Failed to send reminder to %s: %s", chat_id, e)


async def execute_agent_cron_job(chat_id: int, prompt: str):
    """
    Executes an AI agent task on a schedule.
    This allows the cron to 'access all tools' by invoking the LangGraph agent.
    Uses an isolated thread_id to avoid polluting the user's main conversation history.
    """
    from core.context import set_context
    from langchain_core.messages import HumanMessage

    logger.info(f"Triggering agentic cron for chat {chat_id}: {prompt}")

    try:
        if not scheduler or not hasattr(scheduler, "bot"):
            logger.error("Scheduler or bot instance not initialized.")
            return

        # 1. Set context for the agent
        set_context(chat_id=chat_id, bot_instance=scheduler.bot)

        # 2. Get the already-compiled graph (from lifespan in main.py)
        from agent.graph import get_compiled_graph

        graph = get_compiled_graph()

        # 3. Invoke the agent with an isolated thread for cron jobs
        # Using a separate thread prevents agentic crons from polluting main chat history
        cron_thread_id = f"cron_{chat_id}"
        config = {"configurable": {"thread_id": cron_thread_id}}
        inputs = {"messages": [HumanMessage(content=prompt)]}

        # 4. Run with a timeout to prevent hanging
        final_event = await asyncio.wait_for(
            _run_agent_stream(graph, inputs, config),
            timeout=AGENT_CRON_TIMEOUT_SECONDS,
        )

        # 5. Extract and clean the last AI message
        if final_event and "messages" in final_event:
            last_msg = final_event["messages"][-1]

            from agent.nodes import strip_thought_blocks

            clean_msg = strip_thought_blocks(last_msg)
            text_to_send = (
                clean_msg.content
                if isinstance(clean_msg.content, str)
                else str(clean_msg.content)
            )

            if text_to_send and text_to_send.strip():
                await scheduler.bot.send_message(
                    chat_id=chat_id,
                    text=text_to_send,
                    parse_mode="Markdown",
                )
                logger.info("Agentic cron response sent.")

    except asyncio.TimeoutError:
        logger.error(
            f"Agentic cron timed out after {AGENT_CRON_TIMEOUT_SECONDS}s: {prompt}"
        )
        try:
            await scheduler.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Scheduled task timed out after {AGENT_CRON_TIMEOUT_SECONDS}s: {prompt[:100]}",
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error executing agentic cron: {e}", exc_info=True)
        try:
            await scheduler.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Scheduled task failed: {str(e)[:200]}",
            )
        except Exception:
            pass


async def _run_agent_stream(graph, inputs, config):
    """Runs graph.astream and returns the final event."""
    final_event = None
    async for event in graph.astream(inputs, config=config, stream_mode="values"):
        final_event = event
    return final_event


def add_reminder(message: str, target_epoch: Any, chat_id: int = None):
    """Adds a reminder job to the persistent scheduler. Support epoch (int/float), ISO string, or datetime."""
    if not scheduler:
        return None, "Scheduler not initialized."

    chat_id = chat_id or settings.DASHBOARD_USER_ID

    # Robust type handling
    if isinstance(target_epoch, (int, float)):
        remind_at = datetime.fromtimestamp(float(target_epoch))
    elif isinstance(target_epoch, str):
        try:
            remind_at = datetime.fromtimestamp(float(target_epoch))
        except ValueError:
            try:
                remind_at = datetime.fromisoformat(target_epoch)
            except ValueError:
                return None, f"Invalid time format: {target_epoch}"
    elif isinstance(target_epoch, datetime):
        remind_at = target_epoch
    else:
        return None, f"Unsupported time type: {type(target_epoch)}"

    now = datetime.now()

    if remind_at <= now:
        if (now - remind_at).total_seconds() < 60:
            remind_at = datetime.fromtimestamp(now.timestamp() + 1)
        else:
            return None, "Time must be in the future."

    job = scheduler.add_job(
        send_reminder_job,
        "date",
        run_date=remind_at,
        args=[chat_id, message],
        misfire_grace_time=3600,
    )

    return job.id, remind_at


def add_recurring_reminder(
    message: str,
    interval_minutes: int = None,
    interval_seconds: int = None,
    cron_expression: str = None,
    chat_id: int = None,
    is_agent_task: bool = False,
):
    """Adds a recurring reminder job (interval or cron) to the persistent scheduler."""
    if not scheduler:
        return None, "Scheduler not initialized."

    chat_id = chat_id or settings.DASHBOARD_USER_ID

    try:
        if interval_minutes:
            trigger = IntervalTrigger(minutes=interval_minutes)
            schedule_desc = (
                f"every {interval_minutes} minute{'s' if interval_minutes != 1 else ''}"
            )
        elif interval_seconds:
            trigger = IntervalTrigger(seconds=interval_seconds)
            schedule_desc = (
                f"every {interval_seconds} second{'s' if interval_seconds != 1 else ''}"
            )
        elif cron_expression:
            trigger = CronTrigger.from_crontab(cron_expression)
            schedule_desc = _humanize_cron(cron_expression)
        else:
            return (
                None,
                "Either interval_minutes, interval_seconds, or cron_expression must be provided.",
            )

        prefix = "remind_agent_" if is_agent_task else "remind_rec_"
        job_id = f"{prefix}{uuid.uuid4().hex[:8]}"
        target_func = execute_agent_cron_job if is_agent_task else send_reminder_job

        job = scheduler.add_job(
            target_func,
            trigger,
            args=[chat_id, message],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info(f"Recurring task set: {message} ({schedule_desc})")
        return job.id, schedule_desc
    except Exception as e:
        logger.error(f"Failed to add recurring task: {e}")
        return None, str(e)


def _humanize_cron(expr: str) -> str:
    """Converts a crontab expression into a human-readable description."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return f"cron '{expr}'"

    minute, hour, dom, month, dow = parts

    # Common patterns
    if expr == "* * * * *":
        return "every minute"
    if minute != "*" and hour != "*" and dom == "*" and month == "*" and dow == "*":
        return f"daily at {hour.zfill(2)}:{minute.zfill(2)}"
    if minute != "*" and hour != "*" and dom == "*" and month == "*" and dow != "*":
        day_map = {
            "0": "Sun",
            "1": "Mon",
            "2": "Tue",
            "3": "Wed",
            "4": "Thu",
            "5": "Fri",
            "6": "Sat",
            "7": "Sun",
        }
        days = ",".join(day_map.get(d, d) for d in dow.split(","))
        return f"at {hour.zfill(2)}:{minute.zfill(2)} on {days}"
    if minute == "0" and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return "every hour"
    if minute == "*/5" and hour == "*":
        return "every 5 minutes"
    if minute == "*/15" and hour == "*":
        return "every 15 minutes"
    if minute == "*/30" and hour == "*":
        return "every 30 minutes"

    return f"cron '{expr}'"


def get_all_reminders():
    """Returns a list of all pending jobs (one-off and recurring crons)."""
    if not scheduler:
        return []

    jobs = scheduler.get_jobs()
    reminder_list = []
    for job in jobs:
        is_recurring = job.id.startswith("remind_rec_") or job.id.startswith(
            "remind_agent_"
        )
        is_agent = job.id.startswith("remind_agent_")

        info = {
            "id": job.id,
            "next_run_time": job.next_run_time,
            "is_recurring": is_recurring,
            "is_agent": is_agent,
            "message": job.args[1] if len(job.args) > 1 else "Unknown",
        }

        if is_recurring:
            info["type"] = "recurring"
            info["schedule"] = _format_trigger(job.trigger)
        else:
            info["type"] = "one-off"
            info["schedule"] = None

        reminder_list.append(info)
    return reminder_list


def _format_trigger(trigger) -> str:
    """Formats an APScheduler trigger into a human-readable string."""
    try:
        if isinstance(trigger, IntervalTrigger):
            secs = int(trigger.interval.total_seconds())
            if secs >= 3600:
                hours = secs // 3600
                return f"Every {hours} hour{'s' if hours != 1 else ''}"
            if secs >= 60:
                mins = secs // 60
                return f"Every {mins} minute{'s' if mins != 1 else ''}"
            return f"Every {secs} second{'s' if secs != 1 else ''}"
        if isinstance(trigger, CronTrigger):
            # Reconstruct from CronTrigger fields
            fields = {f.name: str(f) for f in trigger.fields}
            expr = f"{fields.get('minute', '*')} {fields.get('hour', '*')} {fields.get('day', '*')} {fields.get('month', '*')} {fields.get('day_of_week', '*')}"
            return _humanize_cron(expr)
    except Exception:
        pass
    return str(trigger)


def delete_reminder(job_id: str):
    """Deletes a reminder job from the scheduler."""
    if not scheduler:
        return False
    try:
        scheduler.remove_job(job_id)
        return True
    except Exception:
        return False


def delete_all_reminders():
    """Alias for clear_all_reminders."""
    return clear_all_reminders()


def clear_all_reminders():
    """Removes all jobs from the scheduler."""
    if not scheduler:
        return False
    try:
        scheduler.remove_all_jobs()
        logger.info("Removed all scheduled jobs.")
        return True
    except Exception as e:
        logger.error(f"Failed to remove all jobs: {e}")
        return False


def shutdown_scheduler():
    """Shut down the scheduler cleanly."""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("APScheduler shut down.")
