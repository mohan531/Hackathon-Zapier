# Slack WebClient initialization and message sending helpers

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests # For response_url
import json # For response_url payload
import logging # Import logging

# Get a logger instance for this module
logger = logging.getLogger(__name__)

# Import Slack specific configs
from config import SLACK_BOT_TOKEN

# Initialize Slack WebClient once
slack_web_client = WebClient(token=SLACK_BOT_TOKEN)

def send_slack_message(channel_id: str, text: str, blocks=None, response_url=None):
    """Sends a message to a Slack channel or responds via response_url."""
    try:
        if response_url:
            payload = {"text": text}
            if blocks:
                payload["blocks"] = blocks
            requests.post(response_url, json=payload, timeout=5)
            logger.info(f"Sent deferred response to Slack channel {channel_id} via response_url.")
        else:
            slack_web_client.chat_postMessage(channel=channel_id, text=text, blocks=blocks)
            logger.info(f"Posted message to Slack channel {channel_id}.")
    except SlackApiError as e:
        logger.error(f"Slack API error when sending message to channel {channel_id}: {e.response['error']}", exc_info=True)
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error when responding to Slack via response_url to channel {channel_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred sending Slack message to channel {channel_id}: {e}", exc_info=True)