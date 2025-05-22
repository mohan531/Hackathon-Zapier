 # For Slack request signature verification

from fastapi import Request, HTTPException
from slack_sdk.signature import SignatureVerifier
import os
import logging # Import logging

# Get a logger instance for this module
logger = logging.getLogger(__name__)


# Import SLACK_SIGNING_SECRET from config
from config import SLACK_SIGNING_SECRET

# Initialize the verifier once
signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET)

async def verify_slack_request(request: Request):
    """Verifies the authenticity of incoming Slack requests."""
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    req_signature = request.headers.get("X-Slack-Signature")
    body_bytes = await request.body() # Read body bytes here

    if not signature_verifier.is_valid_request(body_bytes.decode('utf-8'), req_signature, timestamp):
        logger.warning(f"Invalid Slack request signature detected from {request.client.host}")
        raise HTTPException(status_code=403, detail="Invalid Slack request signature")
    logger.debug(f"Slack request signature verified from {request.client.host}") 
    return body_bytes 