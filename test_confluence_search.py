# test_confluence_search.py

import logging
import os
import sys

# Add the project root to the Python path to allow absolute imports from 'app'
# This is a common pattern for standalone scripts within a larger project
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))


# Setup logging first for visibility
from app.core.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# Import the Confluence client
from app.integrations.confluence.client import search_confluence_pages

def run_confluence_search_test():
    """
    Runs a direct test of the Confluence search functionality.
    """
    logger.info("Starting Confluence search test...")

    test_query = "kafka" # Change this to a relevant search query for your Confluence instance

    try:
        results = search_confluence_pages(test_query)

        if results and results.get('results'):
            logger.info(f"Successfully found {len(results['results'])} results for query: '{test_query}'")
            for i, page in enumerate(results['results']):
                title = page.get('title', 'Untitled Page')
                page_id = page.get('id', 'N/A')
                # Construct permalink if available
                page_url = None
                if '_links' in page and 'webui' in page['_links']:
                    page_url = page['_links']['webui']
                elif '_links' in page and 'base' in page['_links'] and 'self' in page['_links']:
                    page_url = f"{page['_links']['base']}{page['_links']['self']}".replace("/rest/api/content", "/display")

                logger.info(f"  {i+1}. Title: '{title}' (ID: {page_id})")
                if page_url:
                    logger.info(f"     URL: {page_url}")
                else:
                    logger.info("     URL: (Not available)")
        elif results and results.get('errorMessage'):
            logger.error(f"Confluence search returned an error: {results['errorMessage']}")
        else:
            logger.info(f"No results found for query: '{test_query}' or unexpected response format.")

    except Exception as e:
        logger.critical(f"An unhandled error occurred during the Confluence search test: {e}", exc_info=True)

if __name__ == "__main__":
    run_confluence_search_test()