"""Configuration management for the Telegram Summary Bot."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')

# Database Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'bot_data.db')

# Session Configuration
SESSION_NAME = os.getenv('SESSION_NAME', 'telegram_session')

# Validate required configuration
def validate_config():
    """Validate that all required configuration is present."""
    required_vars = {
        'BOT_TOKEN': BOT_TOKEN,
        'API_ID': API_ID,
        'API_HASH': API_HASH,
        'OPENROUTER_API_KEY': OPENROUTER_API_KEY,
    }

    missing = [var for var, value in required_vars.items() if not value]

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please copy .env.example to .env and fill in the values."
        )
