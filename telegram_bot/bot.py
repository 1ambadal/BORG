import os
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from core.config import settings
from core.context import set_context
from agent.agent import get_agent_response

logger = logging.getLogger(__name__)


def get_draft_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Send", callback_data="confirm_send"),
            InlineKeyboardButton("Cancel", callback_data="cancel_send"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles button clicks for Yes/Cancel on drafts.
    """
    query = update.callback_query
    await query.answer()

    choice = query.data
    user_input = "Yes" if choice == "confirm_send" else "Cancel"

    await query.edit_message_reply_markup(reply_markup=None)

    set_context(chat_id=update.effective_chat.id, bot_instance=context.bot)

    response_text = await get_agent_response(user_input)

    if response_text and response_text.strip():
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=response_text
        )


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles voice messages by transcribing them and passing text to the agent.
    """
    try:
        import uuid
        from services.audio_service import transcribe_audio

        voice = update.message.voice or update.message.audio
        file_id = voice.file_id
        new_file = await context.bot.get_file(file_id)

        temp_filename = f"temp_voice_{uuid.uuid4()}.ogg"
        await new_file.download_to_drive(temp_filename)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎧 Listening... Processing your audio...",
        )

        transcribed_text = transcribe_audio(temp_filename)

        if os.path.exists(temp_filename):
            os.remove(temp_filename)

        if transcribed_text.startswith("Error"):
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=f"⚠️ {transcribed_text}"
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'🎤 Transcribed: "{transcribed_text}"',
        )

        set_context(chat_id=update.effective_chat.id, bot_instance=context.bot)

        start_time = time.time()
        response_text = await get_agent_response(transcribed_text)

        if response_text and response_text.strip():
            reply_markup = (
                get_draft_keyboard()
                if "Draft Email Generated:" in response_text
                else None
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response_text,
                reply_markup=reply_markup,
            )

        duration = time.time() - start_time
        logger.info(f"Voice message processed in {duration:.2f}s")

    except Exception as e:
        logger.error(f"Error handling voice message: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, I encountered an error while processing your voice message.",
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    welcome_message = (
        f"BORG online. Welcome, {user_first_name}.\n\n"
        "I am your personal operating system, configured for:\n"
        "• Schedule & Reminders — Calendar, tasks, and alerts\n"
        "• Personal Tracking — Workouts, nutrition, and finance\n"
        "• Knowledge Vault — Bookmarks, facts, and brain dumps\n"
        "• Career & Research — Job scraping, skill gaps, and email drafting\n\n"
        "Upload a resume or start chatting to begin."
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=welcome_message
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_id = document.file_id
    file_name = document.file_name

    if not (file_name.lower().endswith(".pdf") or file_name.lower().endswith(".docx")):
        await update.message.reply_text(
            "Please upload a PDF or DOCX file for your resume."
        )
        return

    try:
        from services.resume_service import save_resume
        from services.db_service import save_message
        from agent.nodes import clear_cache

        new_file = await context.bot.get_file(file_id)
        file_content = await new_file.download_as_bytearray()

        result = await save_resume(file_content, file_name)

        content_text = result.get("content_text", "")

        save_message(
            thread_id="1",
            role="human",
            content=f"[Uploaded Resume File: {file_name}]"
        )

        if not content_text:
            reply_text = "✅ Resume saved, but I had trouble reading the text. Please ensure it is a valid PDF or DOCX."
            await update.message.reply_text(reply_text)
            save_message(thread_id="1", role="ai", content=reply_text)
        else:
            reply_text = (
                "✅ Resume received and processed!\n\n"
                "I've also generated a generic cover letter for you."
            )
            await update.message.reply_text(reply_text)
            save_message(thread_id="1", role="ai", content=reply_text)

        clear_cache("1")
    except Exception as e:
        logger.error(f"Failed to handle document: {e}", exc_info=True)
        await update.message.reply_text("Failed to save your resume. Please try again.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        set_context(chat_id=update.effective_chat.id, bot_instance=context.bot)

        response_text = await get_agent_response(user_message)

        if response_text and response_text.strip():
            reply_markup = (
                get_draft_keyboard()
                if "Draft Email Generated:" in response_text
                else None
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response_text,
                reply_markup=reply_markup,
            )
        else:
            logger.warning(
                "Received empty response_text from agent. Skipping message send."
            )

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, I encountered an error while processing your request.",
        )


async def fresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Nuclear reset command.
    """
    from agent.tools import reset_user_data_tool

    set_context(chat_id=update.effective_chat.id, bot_instance=context.bot)

    response_text = reset_user_data_tool.invoke({})
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)


def create_bot_app():
    application = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("fresh", fresh))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    )
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_message)
    )

    return application
