# Confluence API client logic (search, get content)

import requests
import json
import base64
from bs4 import BeautifulSoup # For future content parsing
import os
import logging # Import logging
from requests.auth import HTTPBasicAuth

# Get a logger instance for this module
logger = logging.getLogger(__name__)

# Import Confluence specific configs
from config import (
    CONFLUENCE_BASE_URL,
    CONFLUENCE_API_TOKEN,
    # CONFLUENCE_USERNAME,
    # CONFLUENCE_PASSWORD,
    SEARCH_RESULTS_LIMIT
)


def _get_confluence_auth_headers():
    """Internal helper to get headers for Confluence API authentication."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if CONFLUENCE_API_TOKEN:
        headers["Authorization"] = f"Bearer {CONFLUENCE_API_TOKEN}"
    # elif CONFLUENCE_USERNAME and CONFLUENCE_PASSWORD:
    #     auth_string = f"{CONFLUENCE_USERNAME}:{CONFLUENCE_PASSWORD}"
    #     encoded_auth = base64.b64encode(auth_string.encode()).decode("ascii")
    #     headers["Authorization"] = f"Basic {encoded_auth}"
    else:
        raise ValueError("Confluence authentication details not provided.")
    return headers


# def search_confluence_pages(query: str):
#     """
#     Searches Confluence pages based on a CQL query and returns top results.
#     We only fetch ID, title, and permalink for now.
#     """
#     cql_query = f'text ~ "{query}" AND type = "page"'
#     encoded_cql = requests.utils.quote(cql_query)
#     search_url = f"{CONFLUENCE_BASE_URL}/rest/api/content/search?cql={encoded_cql}&limit={SEARCH_RESULTS_LIMIT}&expand=space"

#     headers = _get_confluence_auth_headers()
#     try:
#         response = requests.get(search_url, headers=headers, timeout=10)
#         response.raise_for_status()
#         logger.info(f"Successfully retrieved search results from Confluence for query: '{query}'")
#         return response.json()
#     except requests.exceptions.RequestException as e:
#         logger.error(f"Error searching Confluence for query '{query}': {e}", exc_info=True)
#         return {"results": [], "errorMessage": str(e)}

def get_confluence_page_content(page_id: str):
    """
    Retrieves the content of a Confluence page in storage format.
    (This function is here for when you enable summarization later)
    """
    content_url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}?expand=body.storage"
    headers = _get_confluence_auth_headers()
    try:
        response = requests.get(content_url, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"Successfully fetched content for Confluence page ID: {page_id}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting content for Confluence page ID {page_id}: {e}", exc_info=True)
        return None

# def extract_plain_text_from_confluence_storage(storage_html: str):
#     """
#     Extracts plain text from Confluence's storage HTML format.
#     (This function is here for when you enable summarization later)
#     """
#     logger.debug("Extracting plain text from Confluence storage format.")
#     soup = BeautifulSoup(storage_html, 'html.parser')
#     for script_or_style in soup(["script", "style"]):
#         script_or_style.extract()
#     text = soup.get_text(separator=' ', strip=True)
#     logger.debug("Plain text extraction complete.")
#     return text


def fetch_confluence_page_api(base_url, page_id, email, api_token):
    """Fetches a Confluence page's content via API."""
    api_url = f"{base_url}/wiki/rest/api/content/{page_id}?expand=body.storage"
    auth = (email, api_token)
    headers = {"Accept": "application/json"}
    resp = requests.get(api_url, auth=auth, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch Confluence page via API: {resp.text}")
    data = resp.json()
    return data["body"]["storage"]["value"]

def extract_plain_text_from_confluence_storage(storage_html):
    """Extracts plain text from Confluence's storage HTML format."""
    soup = BeautifulSoup(storage_html, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.extract()
    return soup.get_text(separator=' ', strip=True)

def search_confluence_pages(query, base_url, email, api_token):
    """Searches Confluence pages based on a query."""
    search_url = f"{base_url}/wiki/rest/api/content/search?cql=text~'{query}'"
    auth = (email, api_token)
    headers = {"Accept": "application/json"}
    resp = requests.get(search_url, auth=auth, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Failed to search Confluence pages: {resp.text}")
    return resp.json()