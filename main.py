# confluence-summarizer-slack-app/main.py

from fastapi import FastAPI
import uvicorn
import logging

# Import the logging setup function
from app.core.logging_config import setup_logging
# Import the routers
from app.routers import slack_events, slack_commands

# --- Initialize Logging ---
setup_logging()
# Get a logger for the main application file
logger = logging.getLogger(__name__)


app = FastAPI()

# Include the routers
app.include_router(slack_events.router, prefix="/slack", tags=["slack_events"])
app.include_router(slack_commands.router, prefix="/slack", tags=["slack_commands"])

@app.get("/")
async def root():
    return {"message": "Confluence Summarizer Slack App is running!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)