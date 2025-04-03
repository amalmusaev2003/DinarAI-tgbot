import os

# Bot configuration
TG_BOT_API_KEY = os.getenv('TG_BOT_API_KEY') or ""
if TG_BOT_API_KEY == "":
    raise ValueError("TG_BOT_API_KEY environment variable is not set")

# API configuration
API_HOST = os.getenv("API_HOST")
if API_HOST is None:
    raise ValueError("API_HOST environment variable is not set")

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Request configuration
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1
API_TIMEOUT = 240  # seconds