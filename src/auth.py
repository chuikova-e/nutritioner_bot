import logging
from config import ALLOWED_USERS


def check_user_access(user_id: int, username: str) -> bool:
    """Check if user is allowed to use the bot"""
    if not username:  # If user doesn't have a username
        logging.warning(f"Access attempt from user without username (ID: {user_id})")
        return False
    if username in ALLOWED_USERS:
        return True
    logging.warning(
        f"Unauthorized access attempt from user @{username} (ID: {user_id})"
    )
    return False
