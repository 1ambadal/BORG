import logging
import os
import base64
from services.llm_service import get_llm
from langchain_core.messages import HumanMessage
from core.config import settings
from agent.prompts import AUDIO_TRANSCRIPTION_PROMPT

logger = logging.getLogger(__name__)


def transcribe_audio(file_path: str) -> str:
    """
    Transcribes an audio file using Google Gemini via LangChain.

    Args:
        file_path: The local path to the audio file.

    Returns:
        The transcribed text.
    """
    try:
        if not os.path.exists(file_path):
            return "Error: Audio file not found locally."

        # Read and encode audio file
        with open(file_path, "rb") as audio_file:
            audio_data = base64.b64encode(audio_file.read()).decode("utf-8")

        # Determine mime type (basic check)
        mime_type = "audio/ogg"
        if file_path.endswith(".mp3"):
            mime_type = "audio/mp3"
        elif file_path.endswith(".wav"):
            mime_type = "audio/wav"

        # Initialize model (consistent with agent)
        llm = get_llm(temperature=0)

        # Prepare content
        message = HumanMessage(
            content=[
                {"type": "text", "text": AUDIO_TRANSCRIPTION_PROMPT},
                {"type": "media", "mime_type": mime_type, "data": audio_data},
            ]
        )

        logger.info(f"Transcribing audio ({mime_type}) using LangChain...")
        response = llm.invoke([message])

        return response.content

    except Exception as e:
        logger.error(f"Failed to transcribe audio: {e}", exc_info=True)
        return f"Error transcribing audio: {str(e)}"
