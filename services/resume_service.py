"""
Resume Service
"""

import os
import logging
from typing import Optional, List, Any, Dict
import docx
import pypdf
from services.db_service import (
    save_resume_entry,
    get_resume_entry,
    upsert_missing_skill,
    get_all_missing_skills,
    clear_resume_table,
)
from services.user_profile_service import save_user_profile
from services.llm_service import get_llm
from core.config import settings
from core.models import UserProfile, SkillList
from agent.prompts import (
    SKILL_GAP_PROMPT,
    COVER_LETTER_SPECIFIC_PROMPT,
    COVER_LETTER_GENERIC_PROMPT,
    PROFILE_BUILDER_PROMPT,
)

logger = logging.getLogger(__name__)

RESUME_DIR = "resumes"


def ensure_resume_dir():
    """
    Ensures the resume directory exists.
    """
    if not os.path.exists(RESUME_DIR):
        os.makedirs(RESUME_DIR)


def delete_all_resumes():
    """
    Deletes all files within the resume directory.
    """
    ensure_resume_dir()
    try:
        if os.path.exists(RESUME_DIR):
            for filename in os.listdir(RESUME_DIR):
                file_path = os.path.join(RESUME_DIR, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            logger.info("Cleared all resume files.")
    except Exception as e:
        logger.error("Error during resume clearing: %s", e)


async def save_resume(file_content: bytes, filename: str) -> Dict[str, str]:
    """Saves the resume file, parses its content, and enforces a global one-resume policy."""

    ensure_resume_dir()
    delete_all_resumes()
    clear_resume_table()

    file_path = os.path.join(RESUME_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(file_content)

    content_text = ""
    try:
        if filename.lower().endswith(".pdf"):
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                content_text += page.extract_text() + "\n"
        elif filename.lower().endswith(".docx"):
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                content_text += para.text + "\n"
        elif filename.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                content_text = f.read()

        content_text = content_text.strip()
    except Exception as e:
        logger.error("Failed to parse resume %s: %s", file_path, e)

    cl_content = ""
    if content_text:
        try:
            cl_content = await generate_cover_letter_content(content_text)
        except Exception as e:
            logger.error("Failed to generate generic CL: %s", e)

    save_resume_entry(file_path, filename, content_text, cl_content)

    try:
        await extract_user_profile(content_text)
    except Exception as e:
        logger.error("Failed to extract user profile from resume: %s", e)

    return {"file_path": file_path, "content_text": content_text}


async def generate_cover_letter_content(
    resume_text: str,
    company_name: Optional[str] = None,
    role_name: Optional[str] = None,
) -> str:
    """
    Generates a cover letter based on the resume.
    If company_name and role_name are provided, generates a specific 'Why me' paragraph.
    Otherwise, generates a generic professional cover letter.
    """
    if not resume_text:
        resume = get_resume_entry()
        resume_text = resume.get("resume_text") if resume else None

    if not resume_text:
        return ""

    llm = get_llm(temperature=0.7)

    if company_name and role_name:
        prompt = COVER_LETTER_SPECIFIC_PROMPT.format(
            resume_text=resume_text, role_name=role_name, company_name=company_name
        )
    else:
        prompt = COVER_LETTER_GENERIC_PROMPT.format(resume_text=resume_text)

    try:
        response = await llm.ainvoke(prompt)
        return response.content
    except Exception as e:
        logger.error("Failed to generate cover letter content: %s", e)
        return ""


def update_skill_tracker(skills_list: list[str]) -> bool:
    """
    Updates the local database with missing skills.
    Increments count for existing skills, adds new ones with count 1.
    Returns: True if successful, False otherwise.
    """
    try:
        success = True
        for skill in skills_list:
            if not upsert_missing_skill(skill):
                success = False

        logger.info("Updated local DB skill tracker with %s skills.", len(skills_list))
        return success

    except Exception as e:
        logger.error("Failed to update local skill tracker: %s", e)
        return False


def get_missing_skills() -> List[Dict[str, Any]]:
    """
    Retrieves the list of missing skills for a user from the database.
    Returns: List of dicts with 'skill' and 'count'.
    """
    try:
        return get_all_missing_skills()
    except Exception as e:
        logger.error("Failed to fetch skills from DB: %s", e)
        return []


async def analyze_skill_gap(job_description: str) -> str:
    """
    Compares the user's resume against a job description to identify missing skills.
    Updates the persistent Excel tracker and returns the list.
    """
    resume = get_resume_entry()
    resume_text = resume.get("resume_text") if resume else None
    if not resume_text:
        return "No resume found. Please upload your resume first."

    llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0.2)
    structured_llm = llm.with_structured_output(SkillList)

    prompt = SKILL_GAP_PROMPT.format(
        resume_text=resume_text, job_description=job_description
    )

    result = await structured_llm.ainvoke(prompt)
    missing_skills = result.skills if result else []

    if missing_skills:
        success = update_skill_tracker(missing_skills)
        if success:
            link_msg = "✅ I have added these to your local Skill Tracker."
        else:
            link_msg = "⚠️ I identified these gaps, but failed to update your tracker."

        display_list = "\n".join([f"- {s}" for s in missing_skills])
        return f"{display_list}\n\n" f"{link_msg}"
    return "Great news! I didn't find any significant missing skills for this role."


async def extract_user_profile(resume_text: str) -> Optional[UserProfile]:
    """Extracts a structured UserProfile from resume text and saves it to a JSON file."""
    if not resume_text:
        return None

    llm = get_llm(model=settings.DEFAULT_FAST_MODEL, temperature=0)
    structured_llm = llm.with_structured_output(UserProfile)

    prompt = PROFILE_BUILDER_PROMPT.format(resume_text=resume_text)
    try:
        profile = await structured_llm.ainvoke(prompt)
        if profile:
            save_user_profile(profile.model_dump())
            return profile
    except Exception as e:
        logger.error("Error extracting user profile: %s", e)

    return None
