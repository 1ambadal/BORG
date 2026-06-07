import os
import logging
import json
from typing import Optional, Dict, Any
from core.config import settings

logger = logging.getLogger(__name__)


def get_profile_path() -> str:
    """Returns the path to the user's profile JSON file."""
    return os.path.join(settings.DB_DIR, "user_profile.json")


def save_user_profile(profile: Dict[str, Any]) -> bool:
    """Saves a user profile to a JSON file."""
    try:
        path = get_profile_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

        logger.info("User profile saved to %s", path)
        return True
    except Exception as e:
        logger.error("Failed to save user profile to JSON: %s", e)
        return False


def load_user_profile() -> Optional[Dict[str, Any]]:
    """Loads a user profile from a JSON file."""
    try:
        path = get_profile_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        return None
    except Exception as e:
        logger.error("Failed to load user profile from JSON: %s", e)
        return None


def delete_all_profile_files() -> bool:
    """Deletes the user's profile JSON file from the DB directory."""
    try:
        path = get_profile_path()
        if os.path.exists(path):
            os.remove(path)
            logger.info("Deleted user profile file: %s", path)
            return True
        return False
    except Exception as e:
        logger.error("Failed to delete user profile file: %s", e)
        return False
