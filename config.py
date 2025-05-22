import os
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# This should be called once at the start of your application.
load_dotenv()

# --- Slack Configuration ---
# Fallback to None if not set, so you can raise an error if critical
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# --- Confluence Configuration ---
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")

# --- Ollama Configuration  ---
# OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2") # Default model

# --- Application Specific Settings ---
# You can define non-secret application settings here, with defaults.
# These could also come from environment variables for production overrides.
SEARCH_RESULTS_LIMIT = int(os.getenv("SEARCH_RESULTS_LIMIT", 5)) # Convert to int

# --- Basic Validation  ---
def validate_config():
    if not SLACK_BOT_TOKEN:
        raise ValueError("SLACK_BOT_TOKEN not set in environment variables or .env file.")
    if not SLACK_SIGNING_SECRET:
        raise ValueError("SLACK_SIGNING_SECRET not set in environment variables or .env file.")
    if not CONFLUENCE_BASE_URL:
        raise ValueError("CONFLUENCE_BASE_URL not set in environment variables or .env file.")
    if not CONFLUENCE_API_TOKEN:

        if not CONFLUENCE_API_TOKEN:
            raise ValueError("CONFLUENCE_API_TOKEN not set in environment variables or .env file.")

# Call validation at module load (or in main)
validate_config()