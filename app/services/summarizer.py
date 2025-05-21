# Orchestrates Confluence search, content extraction, and (future) LLM summary

from slack_sdk.models.blocks import SectionBlock, DividerBlock, TextObject
import requests
import asyncio
import os
import logging # Import logging

# Get a logger instance for this module
logger = logging.getLogger(__name__)

# Import integrations
from app.integrations.confluence.client import search_confluence_pages, get_confluence_page_content, extract_plain_text_from_confluence_storage
from app.integrations.slack.client import send_slack_message


async def process_confluence_search_command(channel_id: str, text_query: str, response_url: str):
    """Orchestrates the Confluence search and sends results to Slack."""
    logger.info(f"Processing Confluence search command for query: '{text_query}' for channel {channel_id}.")
    try:
        search_results_data = search_confluence_pages(text_query)

        if search_results_data.get('errorMessage'):
            logger.error(f"Confluence search failed for '{text_query}': {search_results_data['errorMessage']}")
            send_slack_message(channel_id, f"Error searching Confluence: {search_results_data['errorMessage']}", response_url=response_url)
            return

        results = search_results_data.get('results', [])

        if not results:
            logger.info(f"No Confluence pages found for '{text_query}'.")
            send_slack_message(channel_id, f"No Confluence pages found for '{text_query}'. Try a different query.", response_url=response_url)
            return

        logger.info(f"Found {len(results)} Confluence pages for query '{text_query}'.")

        blocks = [
            SectionBlock(
                text=f"*Confluence Search Results for '{text_query}':*"
            ),
            DividerBlock()
        ]

        for i, page in enumerate(results):
            title = page.get('title', 'Untitled Page')
            page_url = None
            if '_links' in page and 'webui' in page['_links']:
                page_url = page['_links']['webui']
            elif '_links' in page and 'base' in page['_links'] and 'self' in page['_links']:
                 page_url = f"{page['_links']['base']}{page['_links']['self']}".replace("/rest/api/content", "/display")

            space_name = page.get('space', {}).get('name', 'N/A')
            space_key = page.get('space', {}).get('key', 'N/A')

            if page_url:
                blocks.append(SectionBlock(
                    text=f"• *<{page_url}|{title}>* (Space: `{space_key}`)"
                ))
            else:
                blocks.append(SectionBlock(
                    text=f"• *{title}* (Space: `{space_key}`) - _Link not found or could not be parsed_"
                ))
            if i < len(results) - 1:
                blocks.append(DividerBlock())

        send_slack_message(channel_id, text=f"Here are the search results for '{text_query}':", blocks=blocks, response_url=response_url)
        logger.info(f"Successfully sent search results to channel {channel_id}.")

    except Exception as e:
        logger.critical(f"A critical error occurred in process_confluence_search_command for query '{text_query}': {e}", exc_info=True)
        send_slack_message(channel_id, f"Sorry, an unexpected error occurred: {e}", response_url=response_url)

# --- Future LLM Summarization Logic (to be added later) ---
def summarize_text(text):
    """Summarizes the given text using an LLM."""
    # Placeholder for LLM integration
    return f"Summary of the text: {text[:100]}..."
