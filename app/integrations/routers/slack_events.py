# Endpoint for Slack event subscriptions (e.g., URL verification)

from fastapi import APIRouter, Request, HTTPException
import json
import logging # Import logging

# Get a logger instance for this module
logger = logging.getLogger(__name__)

# Import security helper
from app.core.security import verify_slack_request

router = APIRouter()

@router.post("/events")
async def slack_events_endpoint(request: Request):
    """Endpoint for Slack event subscriptions (e.g., URL verification)."""
    # Verify the request signature
    body_bytes = await verify_slack_request(request)
    data = json.loads(body_bytes)

    # Handle URL verification challenge
    if data.get("type") == "url_verification":
        logger.info("Received Slack URL verification challenge.")
        return {"challenge": data.get("challenge")}

    # For now, just print other events. Expand as needed for future features.
    logger.info(f"Received unhandled Slack event type: {data.get('type')}. Full event: {data}")

    return {"status": "ok"}