import pathlib
import textwrap
import google.generativeai as genai
import os
import requests
import re
# New imports for .env and Google API
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Load environment variables from .env if present
load_dotenv(dotenv_path=Path('.') / '.env')

# from google.colab import userdata  # Not needed outside Colab
# from IPython.display import Markdown, display  # Not needed outside Colab

def text_to_markdown(text):
    text = text.replace(".", "*")
    return textwrap.indent(text, '>', predicate=lambda _: True)

# Set your Gemini API key
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

# Google Docs API scopes and token path
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json'  # Download this from Google Cloud Console

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]

app = App(token=SLACK_BOT_TOKEN)

def fetch_google_doc(doc_url):
    # Try public export first
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", doc_url)
    if not match:
        raise ValueError("Invalid Google Doc URL")
    doc_id = match.group(1)
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    resp = requests.get(export_url)
    if resp.status_code == 200:
        return resp.text
    # If not public, try Google Drive API
    return fetch_private_google_doc(doc_id)

def fetch_private_google_doc(doc_id):
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    service = build('drive', 'v3', credentials=creds)
    # Export as plain text
    resp = service.files().export(fileId=doc_id, mimeType='text/plain').execute()
    return resp.decode('utf-8') if isinstance(resp, bytes) else resp

def fetch_confluence_page_api(base_url, page_id, email, api_token):
    api_url = f"{base_url}/wiki/rest/api/content/{page_id}?expand=body.storage"
    auth = (email, api_token)
    headers = {"Accept": "application/json"}
    resp = requests.get(api_url, auth=auth, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch Confluence page via API: {resp.text}")
    data = resp.json()
    html = data["body"]["storage"]["value"]
    text = re.sub('<[^<]+?>', '', html)
    return text

def resolve_short_link_to_page_id(base_url, short_link, email, api_token):
    url = f"{base_url}/wiki{short_link}"
    auth = (email, api_token)
    resp = requests.get(url, auth=auth)
    if resp.status_code != 200:
        raise Exception("Failed to resolve short link. Make sure the link is correct and you have access.")
    match = re.search(r'contentId=(\d+)', resp.text)
    if match:
        return match.group(1)
    match = re.search(r'/pages/(viewpage\.action\?pageId=(\d+))', resp.text)
    if match:
        return match.group(2)
    raise Exception("Could not resolve page ID from short link.")

def fetch_confluence_page(url, email=None, api_token=None):
    match_page = re.search(r'(https://[^/]+)/wiki/pages/viewpage\\.action\\?pageId=(\\d+)', url)
    match_short = re.search(r'(https://[^/]+)/wiki(/x/[^/?#]+)', url)
    if match_page:
        base_url = match_page.group(1)
        page_id = match_page.group(2)
    elif match_short:
        base_url = match_short.group(1)
        short_link = match_short.group(2)
        if not email or not api_token:
            raise Exception("Authentication required to resolve short link for private pages.")
        page_id = resolve_short_link_to_page_id(base_url, short_link, email, api_token)
    else:
        resp = requests.get(url)
        if resp.status_code != 200:
            raise Exception("Failed to fetch Confluence page. Make sure it is public or provide authentication.")
        text = re.sub('<[^<]+?>', '', resp.text)
        return text
    if not email or not api_token:
        raise Exception("Email and API token required for private Confluence pages.")
    return fetch_confluence_page_api(base_url, page_id, email, api_token)

def is_error_page(text):
    error_signatures = [
        "enable JavaScript", "log in", "not authorized", "couldn't be loaded", "error", "Atlassian"  # add more as needed
    ]
    return any(sig.lower() in text.lower() for sig in error_signatures)

def summarize_text(text):
    prompt = (
        "You are an expert technical writer. Read the following content and provide a structured summary. "
        "Your summary should include:\n"
        "1. A TL;DR (1-2 sentences)\n"
        "2. Key Points (bulleted list)\n"
        "3. Action Items (if any, as a bulleted list)\n"
        "If the content is not useful or looks like an error page, say so.\n\n"
        f"Content:\n{text}"
    )
    response = model.generate_content(prompt)
    return response.text


def fetch_confluence_page_content(page_id, base_url, email, api_token):
    api_url = f'{base_url}/wiki/rest/api/content/{page_id}?expand=body.storage'
    auth = (email, api_token)
    headers = {"Accept": "application/json"}
    resp = requests.get(api_url, auth=auth, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch Confluence page: {resp.text}")
    data = resp.json()
    html = data["body"]["storage"]["value"]
    # Remove HTML tags for summarization
    text = re.sub('<[^<]+?>', '', html)
    return text

def extract_baseurl_and_pageid(url, email=None, api_token=None):
    # Always use static base URL and static page ID for testing
    base_url = "https://testhack.atlassian.net"
    page_id = "491522"
    return base_url, page_id

@app.command("/summarize_channel")
def handle_summarize_channel(ack, body, client, respond):
    ack()
    channel_id = body["channel_id"]
    user_id = body["user_id"]

    # Fetch recent messages (e.g., last 100)
    result = client.conversations_history(channel=channel_id, limit=100)
    messages = result["messages"]
    # Concatenate text, skipping bot messages and empty text
    conversation = "\n".join(
        m.get("text", "") for m in reversed(messages) if m.get("text") and not m.get("subtype")
    )
    if not conversation.strip():
        respond("No messages to summarize.")
        return

    # Summarize using Gemini
    summary = summarize_text(conversation[:8000])  # Limit to 8k chars for Gemini
    # Respond in channel (or DM if you prefer)
    respond(f"*Channel Summary:*\n{summary}")

@app.event("app_mention")
def handle_mention_summarize(event, say, client):
    text = event.get("text", "").lower()
    channel_id = event["channel"]
    user_id = event["user"]
    if "summarize" in text:
        # Fetch recent messages (e.g., last 100)
        result = client.conversations_history(channel=channel_id, limit=100)
        messages = result["messages"]
        # Concatenate text, skipping bot messages and empty text
        conversation = "\n".join(
            m.get("text", "") for m in reversed(messages) if m.get("text") and not m.get("subtype")
        )
        if not conversation.strip():
            say("No messages to summarize.")
            return
        # Summarize using Gemini
        summary = summarize_text(conversation[:8000])  # Limit to 8k chars for Gemini
        say(f"*Channel Summary:*\n{summary}")

@app.event("member_joined_channel")
def handle_member_joined_channel(body, event, client, logger):
    user_id = event["user"]
    logger.info(f"User {user_id} joined a channel, triggering DM onboarding.")
    try:
        dm_channel = client.conversations_open(users=user_id)["channel"]["id"]
        client.chat_postMessage(
            channel=dm_channel,
            text=f"Welcome! Are you a new joiner?",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": f"Welcome to the workspace, <@{user_id}>! Are you a *new joiner*?"}},
                {"type": "actions", "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Yes"}, "value": "new_joiner_yes", "action_id": "new_joiner_yes"},
                    {"type": "button", "text": {"type": "plain_text", "text": "No"}, "value": "new_joiner_no", "action_id": "new_joiner_no"}
                ]}
            ]
        )
        logger.info(f"Sent DM to user {user_id} in channel {dm_channel}.")
        user_state[user_id] = {"awaiting_new_joiner": True}
    except Exception as e:
        logger.error(f"Failed to DM user {user_id}: {e}")

def main():
    url = input("Enter a Confluence or Google Doc link (or just your Confluence base URL to browse): ").strip()
    email = os.environ.get("ATLASSIAN_EMAIL")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN")
    if ("atlassian.net/wiki" in url or "confluence" in url) and (not email or not api_token):
        print("Error: To access private Confluence pages, you must set ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN as environment variables.")
        print("Example:")
        print("  export ATLASSIAN_EMAIL=your.email@domain.com")
        print("  export ATLASSIAN_API_TOKEN=your_api_token")
        return
    try:
        if "docs.google.com/document" in url:
            content = fetch_google_doc(url)
            if is_error_page(content):
                print("Warning: The fetched content looks like an error page or access is restricted. The summary may not be meaningful.\n")
            summary = summarize_text(content[:8000])  # Limit to 8k chars for demo
            print("\n===== SUMMARY =====\n")
            print(text_to_markdown(summary))
            print("\n===================\n")
        elif "atlassian.net/wiki" in url or "confluence" in url:
            base_url, page_id = extract_baseurl_and_pageid(url, email, api_token)
            content = fetch_confluence_page_content(page_id, base_url, email, api_token)
            summary = summarize_text(content[:8000])  # Limit to 8k chars for demo
            print("\n===== SUMMARY =====\n")
            print(text_to_markdown(summary))
            print("\n===================\n")
        
        else:
            print("Unsupported URL. Please provide a Google Doc or Confluence link, or your Confluence base URL to browse.")
            return
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
    