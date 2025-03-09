import os
from dotenv import load_dotenv

# Load environment variables from .env file
if os.path.exists('.env'):
    load_dotenv()

# Get API keys from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Check for required keys
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_TOKEN and OPENAI_API_KEY must be specified in the .env file") 