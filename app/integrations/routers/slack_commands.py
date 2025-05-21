# Endpoint for Slack slash commands

from fastapi import APIRouter, Request, HTTPException
from slack_sdk.models.blocks import SectionBlock, DividerBlock
import json
import logging # Import logging

# Get a logger instance for this module
logger = logging.getLogger(__name__)
# Import services and integrations
from app.core.security import verify_slack_request
from app.integrations.slack.client import send_slack_message
from app.services.summarizer import process_confluence_search_command # We'll create this next

router = APIRouter()


@router.post("/commands")
async def slack_commands_endpoint(request: Request):
    """Endpoint for Slack slash commands."""
    # Verify the request signature
    body_bytes = await verify_slack_request(request) # Slack sends command data as form-urlencoded
    form_data = await request.form()

    channel_id = form_data.get("channel_id")
    user_name = form_data.get("user_name")
    command = form_data.get("command")
    text_query = form_data.get("text")
    response_url = form_data.get("response_url")

    logger.info(f"Received command '{command}' from user '{user_name}' in channel '{channel_id}' with text: '{text_query}'")
    # Acknowledge the command immediately (within 3 seconds)
    send_slack_message(channel_id, f"Searching Confluence for '{text_query}'...", response_url=response_url)

    try:
        # Process the command in a background task (or directly for quick responses)
        # For a hackathon, directly calling the service is often fine unless it's truly long-running.
        # If the task is long-running (e.g., LLM generation), you'd use background tasks like
        # FastAPI's BackgroundTasks or a proper task queue (Celery/RQ).
        await process_confluence_search_command(
            channel_id=channel_id,
            text_query=text_query,
            response_url=response_url
        )
        logger.info(f"Finished processing command '{command}' for '{text_query}'.")
    except Exception as e:
        logger.error(f"Unhandled error processing command '{command}' for '{text_query}': {e}", exc_info=True)
        send_slack_message(channel_id, f"Sorry, an unexpected error occurred while processing your request.", response_url=response_url)
    
    return "OK" # Respond to Slack's command request