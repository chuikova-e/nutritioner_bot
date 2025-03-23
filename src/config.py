import os
from dotenv import load_dotenv

# Load environment variables from .env file
if os.path.exists(".env"):
    load_dotenv()

# Get API keys from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# List of allowed usernames
ALLOWED_USERS = [
    username.strip()
    for username in os.getenv("ALLOWED_USERS", "").split(",")
    if username.strip()
]

# OpenAI configuration
GPT_MODEL = os.getenv(
    "GPT_MODEL", "gpt-4-vision-preview"
)  # Default to GPT-4 Vision if not specified

# Check for required keys
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError(
        "TELEGRAM_TOKEN and OPENAI_API_KEY must be specified in the .env file"
    )

# Add LOG_LEVEL
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # Default to INFO if not specified
