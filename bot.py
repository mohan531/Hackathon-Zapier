import os
import yaml
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.workflows.step import WorkflowStep
from app import summarize_text, fetch_google_doc, fetch_confluence_page_content, extract_baseurl_and_pageid

# Load Slack credentials from environment
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

# Load team links from YAML
with open("teams.yaml", "r") as f:
    TEAM_LINKS = yaml.safe_load(f)

# Load channel mapping from YAML (now channel IDs)
with open("channels.yaml", "r") as f:
    CHANNEL_MAP = yaml.safe_load(f)

# Load error patterns from YAML
with open("errors.yaml", "r") as f:
    ERRORS = yaml.safe_load(f)["errors"]

app = App(token=SLACK_BOT_TOKEN)

# Store user state in memory (for demo; use a DB for production)
user_state = {}

def get_dm_channel_id(client, user_id):
    response = client.conversations_open(users=user_id)
    return response["channel"]["id"]

def search_error_patterns(error_text):
    for entry in ERRORS:
        if entry["pattern"].lower() in error_text.lower():
            return entry["resolution"]
    return None

@app.action("new_joiner_yes")
def handle_new_joiner_yes(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    team_options = [
        {"text": {"type": "plain_text", "text": team}, "value": team}
        for team in TEAM_LINKS.keys()
    ]
    dm_channel = get_dm_channel_id(client, user_id)
    client.chat_postMessage(
        channel=dm_channel,
        text="Which team(s) do you belong to?",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": "Which team(s) do you belong to?"},
             "accessory": {
                 "type": "multi_static_select",
                 "placeholder": {"type": "plain_text", "text": "Select team(s)"},
                 "options": team_options,
                 "action_id": "select_teams"
             }}
        ]
    )
    user_state[user_id] = {"awaiting_team_dropdown": True}

@app.action("new_joiner_no")
def handle_new_joiner_no(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    dm_channel = get_dm_channel_id(client, user_id)
    client.chat_postMessage(
        channel=dm_channel,
        text="Do you have a specific doubt or error?",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": "Do you have a specific *doubt* or *error*?"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Yes"}, "value": "has_doubt_yes", "action_id": "has_doubt_yes"},
                {"type": "button", "text": {"type": "plain_text", "text": "No"}, "value": "has_doubt_no", "action_id": "has_doubt_no"}
            ]}
        ]
    )
    user_state[user_id] = {"awaiting_doubt": True}

@app.action("has_doubt_yes")
def handle_has_doubt_yes(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    dm_channel = get_dm_channel_id(client, user_id)
    client.chat_postMessage(
        channel=dm_channel,
        text="Please describe your error or paste the error message."
    )
    user_state[user_id] = {"awaiting_error": True}

@app.action("has_doubt_no")
def handle_has_doubt_no(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    dm_channel = get_dm_channel_id(client, user_id)
    client.chat_postMessage(
        channel=dm_channel,
        text="Okay! Let me know if you need anything else."
    )
    user_state.pop(user_id, None)

@app.action("select_teams")
def handle_select_teams(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    selected_teams = [opt["value"] for opt in body["actions"][0]["selected_options"]]
    all_links = []
    all_channels = set()
    for team in selected_teams:
        links = TEAM_LINKS.get(team, [])
        all_links.extend(links)
        team_channels = CHANNEL_MAP.get(team, [])
        all_channels.update(team_channels)
    common_channels = CHANNEL_MAP.get("common", [])
    all_channels.update(common_channels)
    invited_channels = []
    for ch_id in all_channels:
        try:
            client.conversations_invite(channel=ch_id, users=user_id)
            invited_channels.append(f"<#{ch_id}>")
        except Exception as e:
            print(f"Failed to invite to {ch_id}: {e}")
    if invited_channels:
        dm_channel = get_dm_channel_id(client, user_id)
        client.chat_postMessage(
            channel=dm_channel,
            text=f"You have been added to these channels: {', '.join(invited_channels)}"
        )
    links_str = "\n".join(f"- {l}" for l in all_links)
    dm_channel = get_dm_channel_id(client, user_id)
    client.chat_postMessage(
        channel=dm_channel,
        text=f"Here are the links for your selected team(s):\n{links_str}\n\nIf you want a summary of any link, reply with the link. Otherwise, say 'done'."
    )
    user_state[user_id] = {"teams": selected_teams, "links": all_links, "awaiting_summarize": True}

@app.event("app_mention")
@app.event("message")
def handle_message_events(body, say, event, context, client):
    user_id = event.get("user")
    text = event.get("text", "").lower()
    channel = event.get("channel")

    # If user is in the middle of a flow, handle it and return
    state = user_state.get(user_id, {})
    if state.get("awaiting_team"):
        # This block is now handled by the dropdown, so skip
        return
    if state.get("awaiting_team_dropdown"):
        # This block is now handled by the dropdown, so skip
        return
    if state.get("awaiting_new_joiner") or state.get("awaiting_summarize") or state.get("awaiting_error") or state.get("awaiting_doubt") or state.get("awaiting_info_or_error"):
        # Let the rest of the function handle the flow as before
        # (the rest of your flow logic is already below)
        pass
    else:
        # If not in a flow, send the initial message
        client.chat_postMessage(
            channel=user_id,
            text="This channel is for getting info related to your team or resolving errors you are facing and if you want to summarize a channel, use /summarize_channel. What do you need help with?",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": "This channel is for getting info related to your *team* or resolving *errors* you are facing. What do you need help with?"}},
                {"type": "actions", "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Team Info"}, "value": "info_team", "action_id": "info_team"},
                    {"type": "button", "text": {"type": "plain_text", "text": "Error Help"}, "value": "info_error", "action_id": "info_error"}
                ]}
            ]
        )
        user_state[user_id] = {"awaiting_info_or_error": True}
        return

    # Existing flow logic below (summarization, error, etc.)
    if state.get("awaiting_error"):
        error_text = text.strip()
        resolution = search_error_patterns(error_text)
        if resolution:
            say(f"Here is a possible resolution for your error:\n*{resolution}*")
        else:
            say("Sorry, I couldn't find a resolution for your error. Please contact support or provide more details.")
        user_state.pop(user_id, None)
        return

    if state.get("awaiting_summarize"):
        if "done" in text:
            say("Okay, let me know if you need anything else!")
            user_state.pop(user_id, None)
            return
        # Clean up the link (remove < > and whitespace, and anything before https)
        link = text.strip().replace("<", "").replace(">", "")
        link = re.sub(r"^[^h]*https", "https", link)  # Remove anything before 'https'
        def base_url(l):
            return re.sub(r'[?#].*$', '', l.strip().replace("<", "").replace(">", ""))
        matched = None
        for l in state["links"]:
            if link == l or base_url(link) == base_url(l) or link.startswith(l):
                matched = l
                break
        if not matched:
            say("Please reply with one of the links I provided (or its base URL), or say 'done'.")
            return
        try:
            if "docs.google.com/document" in link:
                content = fetch_google_doc(link)
            elif "atlassian.net/wiki" in link or "confluence" in link:
                email = os.environ.get("ATLASSIAN_EMAIL")
                api_token = os.environ.get("ATLASSIAN_API_TOKEN")
                base_url_val, page_id = extract_baseurl_and_pageid(link, email, api_token)
                content = fetch_confluence_page_content(page_id, base_url_val, email, api_token)
            else:
                say("Unsupported link type for summarization.")
                return
            summary = summarize_text(content[:8000])
            say(f"Here is the summary for <{link}>:\n```{summary}```")
            # Prompt for another link or done
            say("You can paste another link to summarize, or reply 'done' if finished.")
        except Exception as e:
            say(f"Error summarizing the link: {e}")
        return

    if state.get("awaiting_doubt"):
        if "yes" in text:
            client.chat_postMessage(
                channel=user_id,
                text="Please describe your error or paste the error message."
            )
            user_state[user_id] = {"awaiting_error": True}
            return
        else:
            client.chat_postMessage(
                channel=user_id,
                text="Okay! Let me know if you need anything else."
            )
            user_state.pop(user_id, None)
            return

@app.action("info_team")
def handle_info_team(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    dm_channel = get_dm_channel_id(client, user_id)
    client.chat_postMessage(
        channel=dm_channel,
        text=f"Are you a new joiner?",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Are you a *new joiner*?"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Yes"}, "value": "new_joiner_yes", "action_id": "new_joiner_yes"},
                {"type": "button", "text": {"type": "plain_text", "text": "No"}, "value": "new_joiner_no", "action_id": "new_joiner_no"}
            ]}
        ]
    )
    user_state[user_id] = {"awaiting_new_joiner": True}

@app.action("info_error")
def handle_info_error(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    dm_channel = get_dm_channel_id(client, user_id)
    client.chat_postMessage(
        channel=dm_channel,
        text="Do you have a specific doubt or error?",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": "Do you have a specific *doubt* or *error*?"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Yes"}, "value": "has_doubt_yes", "action_id": "has_doubt_yes"},
                {"type": "button", "text": {"type": "plain_text", "text": "No"}, "value": "has_doubt_no", "action_id": "has_doubt_no"}
            ]}
        ]
    )
    user_state[user_id] = {"awaiting_doubt": True}

@app.command("/summarize_channel")
def handle_summarize_channel(ack, body, client, respond):
    ack()
    channel_id = body["channel_id"]
    user_id = body["user_id"]
    
    # Fetch up to 1000 recent messages using pagination
    messages = []
    cursor = None
    while len(messages) < 1000:
        result = client.conversations_history(
            channel=channel_id,
            limit=min(200, 1000 - len(messages)),
            cursor=cursor
        )
        messages.extend(result["messages"])
        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    # Concatenate text, skipping bot messages and empty text
    conversation = "\n".join(
        m.get("text", "") for m in reversed(messages) if m.get("text") and not m.get("subtype")
    )
    if not conversation.strip():
        respond("No messages to summarize.")
        return
    # Summarize using Gemini
    summary = summarize_text(conversation[:8000])  # Limit to 8k chars for Gemini
    respond(f"*Channel Summary:*{summary}")

@app.event("member_joined_channel")
def handle_member_joined_channel(event, client, logger):
    user_id = event["user"]
    channel_id = event["channel"]
    # Check if the channel is private
    channel_info = client.conversations_info(channel=channel_id)["channel"]
    if not channel_info.get("is_private"):
        return  # Only trigger for private channels
    try:
        dm_channel = get_dm_channel_id(client, user_id)
        client.chat_postMessage(
            channel=dm_channel,
            text=f"Welcome to JumpCloud! Are you a new joiner?",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": f"Welcome to JumpCloud, <@{user_id}>! Are you a *new joiner*?"}},
                {"type": "actions", "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Yes"}, "value": "new_joiner_yes", "action_id": "new_joiner_yes"},
                    {"type": "button", "text": {"type": "plain_text", "text": "No"}, "value": "new_joiner_no", "action_id": "new_joiner_no"}
                ]}
            ]
        )
        user_state[user_id] = {"awaiting_new_joiner": True}
    except Exception as e:
        logger.error(f"Failed to DM user {user_id}: {e}")

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start() 