import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from telegram import Update
from telegram_bot.bot import create_bot_app
from core.config import settings
from services.db_service import init_db
from services.reminder_service import init_scheduler, shutdown_scheduler
from api_routes import router as api_router
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from agent.graph import compile_graph

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("psycopg").setLevel(logging.WARNING)
logging.getLogger("psycopg.pool").setLevel(logging.WARNING)

# Configure logging cleanly
root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
else:
    root_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Global Telegram application instance initialized lazily on startup
ptb_application = None


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """
    Manages the startup and shutdown lifecycle of the FastAPI application,
    including initializing the database, LangGraph persistence, and the Telegram bot.
    """
    global ptb_application
    
    # Initialize Database
    init_db()
    
    # Initialize Telegram Bot Application
    ptb_application = create_bot_app()

    logger.info("Starting up bot...")
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found in .env file")

    async with AsyncConnectionPool(
        settings.DATABASE_URL,
        kwargs={"autocommit": True, "prepare_threshold": None}
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        compile_graph(checkpointer)
        logger.info("LangGraph compiled with AsyncPostgresSaver persistence.")
        if not settings.WEBHOOK_URL:
            raise ValueError("WEBHOOK_URL environment variable is required for strict webhook mode.")

        try:
            await ptb_application.bot.set_webhook(url=f"{settings.WEBHOOK_URL}/webhook")
            logger.info(f"Telegram webhook set successfully to: {settings.WEBHOOK_URL}/webhook")
        except Exception as e:
            logger.critical(f"Failed to set Telegram webhook: {e}")
            raise e

        async with ptb_application:
            await ptb_application.start()
            init_scheduler(ptb_application.bot)
            yield
            shutdown_scheduler()

            await ptb_application.stop()
            await ptb_application.shutdown()
    logger.info("Shutting down bot...")


app = FastAPI(lifespan=lifespan)

# Include the dashboard API routes
app.include_router(api_router, prefix="/api")


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Handle incoming Telegram updates by putting them into the `update_queue`
    """
    await ptb_application.update_queue.put(
        Update.de_json(data=await request.json(), bot=ptb_application.bot)
    )
    return {"status": "ok"}

resumes_dir = os.path.join(os.path.dirname(__file__), "resumes")
if os.path.exists(resumes_dir):
    app.mount("/resumes", StaticFiles(directory=resumes_dir), name="resumes")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
