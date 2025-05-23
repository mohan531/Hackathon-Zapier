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

#load online resources
with open("resources.yaml", "r") as f:
    yaml_data = yaml.safe_load(f)
    RESOURCES = yaml_data["resources"]

# Load team checklists from YAML
with open("teams.yaml", "r") as f:
    TEAM_DATA = yaml.safe_load(f)

app = App(token=SLACK_BOT_TOKEN)

# Store user state in memory (for demo; use a DB for production)
user_state = {}

def get_team_checklist(team_name):
    team = TEAM_DATA.get(team_name)
    if team and isinstance(team, list):
        # Old format, no checklist
        return None
    if team and "checklist" in team:
        return team["checklist"]
    return None

DEFAULT_CHECKLIST = [
    "Set up your email account",
    "Read the employee handbook",
    "Join all relevant Slack channels",
    "Schedule a 1:1 with your manager",
    "Complete security training",
    "Access internal documentation",
    "Introduce yourself in #general"
]

def get_dm_channel_id(client, user_id):
    response = client.conversations_open(users=user_id)
    return response["channel"]["id"]

def search_error_patterns(error_text):
    for entry in ERRORS:
        if entry["pattern"].lower() in error_text.lower():
            return entry["resolution"]
    return None

def format_links_with_priority(links):
    # links: list of dicts with 'url' and 'priority'
    sorted_links = sorted(links, key=lambda l: l.get('priority', 99))
    first = [l['url'] for l in sorted_links if l.get('priority', 99) == 1]
    next_ = [l['url'] for l in sorted_links if l.get('priority', 99) != 1]
    msg = ""
    if first:
        msg += "*Go through these first:*\n" + "\n".join(f"- {url}" for url in first) + "\n"
    if next_:
        msg += "*Then look at these:*\n" + "\n".join(f"- {url}" for url in next_)
    return msg

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
        # Use only the 'links' list for each team
        team_data = TEAM_LINKS.get(team, {})
        team_links = team_data.get('links', []) if isinstance(team_data, dict) else team_data
        all_links.extend(team_links)
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
    # Format links with priority
    links_str = format_links_with_priority(all_links)
    dm_channel = get_dm_channel_id(client, user_id)
    client.chat_postMessage(
        channel=dm_channel,
        text=f"Here are the links for your selected team(s):\n{links_str}\n\nIf you want a summary of any link, reply with the link. Otherwise, say 'done'."
    )
    user_state[user_id] = {"teams": selected_teams, "links": [l['url'] for l in all_links if isinstance(l, dict) and 'url' in l], "awaiting_summarize": True}

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
        def extract_page_id(url):
            match = re.search(r"/pages/(\d+)", url)
            if match:
                return match.group(1)
            match = re.search(r"/pages/.+?pageId=(\d+)", url)
            if match:
                return match.group(1)
            match = re.search(r"/(\d+)", url)
            if match:
                return match.group(1)
            return None
        matched = None
        for l in state["links"]:
            if extract_page_id(link) and extract_page_id(link) == extract_page_id(l):
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
def handle_summarize_channel(ack, body, client, respond, context):
    ack()
    channel_id = body["channel_id"]
    print("Channel ID used in conversations_history:", channel_id)
    user_id = body["user_id"]
    text = body.get("text", "").strip()
    thread_ts = None
    # 1. If user provides a thread_ts argument, use it
    if text:
        thread_ts = text.split()[0]
    # 2. Otherwise, try to get thread_ts from context (if used as a reply in a thread)
    if not thread_ts:
        message = body.get("message") or body.get("container", {})
        thread_ts = message.get("thread_ts") or message.get("ts")
    if thread_ts and thread_ts != body.get("trigger_id"):  # If we have a thread_ts, summarize the thread
        result = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=1000)
        messages = result.get("messages", [])
        conversation = "\n".join(
            m.get("text", "") for m in messages if m.get("text") and not m.get("subtype")
        )
        if not conversation.strip():
            respond("No messages to summarize in this thread.")
            return
        summary = summarize_text(conversation[:8000])
        respond(f"*Thread Summary:*\n{summary}")
        return
    # Otherwise, summarize the channel
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
    conversation = "\n".join(
        m.get("text", "") for m in reversed(messages) if m.get("text") and not m.get("subtype")
    )
    if not conversation.strip():
        respond("No messages to summarize.")
        return
    summary = summarize_text(conversation[:8000])
    respond(f"*Channel Summary:*{summary}")

    # Suggest contextual resources
    suggestions = suggest_resources(conversation[:8000], RESOURCES)
    print("Suggestions from suggest_resources:", suggestions)
    if suggestions:
        respond("*📚 Helpful Resources Based on the Summary:*")
        for suggestion in suggestions:
            respond(suggestion)
    else:
        respond("Nothing to Suggest!!! Carry On ")

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

@app.event("channel_created")
def handle_channel_created(event, client, logger):
    channel = event["channel"]
    channel_name = channel["name"]
    channel_id = channel["id"]

    # Load channels.yaml
    with open("channels.yaml", "r") as f:
        channels_map = yaml.safe_load(f)

    # Match if the team name (key) is a substring of the channel name
    updated = False
    for team in channels_map:
        if team.lower() in channel_name.lower():
            if channel_id not in channels_map[team]:
                channels_map[team].append(channel_id)
                updated = True
                logger.info(f"Added channel {channel_id} to team: {team}")
    if updated:
        with open("channels.yaml", "w") as f:
            yaml.safe_dump(channels_map, f)

@app.shortcut("summarize_thread_action")
def handle_summarize_thread_action(ack, shortcut, client, respond):
    ack()
    channel_id = shortcut["channel"]["id"]
    message_ts = shortcut["message"]["ts"]
    # Use thread_ts if present, else use message_ts (for single-message threads)
    thread_ts = shortcut["message"].get("thread_ts", message_ts)
    # Fetch all messages in the thread
    result = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=1000)
    messages = result.get("messages", [])
    # Concatenate text, skipping bot messages and empty text
    conversation = "\n".join(
        m.get("text", "") for m in messages if m.get("text") and not m.get("subtype")
    )
    if not conversation.strip():
        respond("No messages to summarize in this thread.")
        return
    # Summarize using Gemini
    summary = summarize_text(conversation[:8000])  # Limit to 8k chars for Gemini
    respond(f"*Thread Summary:*\n{summary}")

    # Suggest contextual resources
    suggestions = suggest_resources(summary, RESOURCES)
    if suggestions:
        respond("*📚 Helpful Resources Based on the Summary:*")
        for suggestion in suggestions:
            respond(suggestion)
    else:
        respond("Nothing to Suggest!!! Carry On ")

def send_sync_button_to_channel(client, id_):
    # If id_ starts with 'U', treat as user ID and open DM
    if id_.startswith('U'):
        dm_channel = get_dm_channel_id(client, id_)
        channel_id = dm_channel
    else:
        channel_id = id_
    client.chat_postMessage(
        channel=channel_id,
        text="Sync channel IDs with teams?",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": "Click the button below to sync channel IDs with teams."}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Sync Channels"}, "action_id": "sync_channels_button"}
            ]}
        ]
    )

@app.action("sync_channels_button")
def handle_sync_channels_button(ack, body, client, logger, respond):
    ack()
    user_id = body["user"]["id"]
    # Fetch all channels
    result = client.conversations_list(types="public_channel,private_channel", limit=1000)
    channels = result["channels"]
    # Load channels.yaml
    with open("channels.yaml", "r") as f:
        channels_map = yaml.safe_load(f)
    updated = False
    for channel in channels:
        channel_name = channel["name"]
        channel_id = channel["id"]
        for team in channels_map:
            if team.lower() in channel_name.lower():
                if channel_id not in channels_map[team]:
                    channels_map[team].append(channel_id)
                    updated = True
                    logger.info(f"Added channel {channel_id} to team: {team}")
    if updated:
        with open("channels.yaml", "w") as f:
            yaml.safe_dump(channels_map, f)
        respond("Channel-to-team sync complete! Updated channels.yaml.")
    else:
        respond("Channel-to-team sync complete! No updates needed.")

@app.command("/send_sync_button")
def handle_send_sync_button(ack, respond, client, body):
    ack()
    id_ = os.environ.get("SYNC_CHANNEL_ID")
    if not id_:
        respond("Please set the SYNC_CHANNEL_ID environment variable.")
        return
    send_sync_button_to_channel(client, id_)
    respond(f"Sync button sent to {'user' if id_.startswith('U') else 'channel'} {id_}.")

@app.event("channel_deleted")
def handle_channel_deleted(event, logger):
    channel_id = event["channel"]
    # Load channels.yaml
    with open("channels.yaml", "r") as f:
        channels_map = yaml.safe_load(f)
    updated = False
    for team, channel_list in channels_map.items():
        if channel_id in channel_list:
            channel_list.remove(channel_id)
            updated = True
            logger.info(f"Removed deleted channel {channel_id} from team: {team}")
    if updated:
        with open("channels.yaml", "w") as f:
            yaml.safe_dump(channels_map, f)

@app.command("/send_onboarding_checklist")
def send_onboarding_checklist_cmd(ack, body, client, respond):
    ack()
    channel_id = body["channel_id"]
    client.chat_postMessage(
        channel=channel_id,
        text="Send onboarding checklist to all members?",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Send onboarding checklist to all members of this channel?*"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Send Canvas Checklist"}, "action_id": "send_canvas_checklist", "value": channel_id}
            ]}
        ]
    )
    respond("Checklist trigger button sent to channel.")

@app.action("send_canvas_checklist")
def handle_send_canvas_checklist(ack, body, client):
    ack()
    channel_id = body["actions"][0]["value"]
    members = []
    try:
        result = client.conversations_members(channel=channel_id)
        members = result["members"]
    except Exception as e:
        client.chat_postMessage(channel=channel_id, text=f"Failed to fetch members: {e}")
        return
    # For demo, ask for team name or use a default (could be improved to map users to teams)
    team_name = "Hydrogen"  # TODO: Replace with logic to determine user's team
    checklist = get_team_checklist(team_name) or DEFAULT_CHECKLIST
    for user_id in members:
        if user_id.startswith("U"):
            dm_channel = get_dm_channel_id(client, user_id)
            canvas_blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": f"📝 {team_name} Onboarding Canvas"}},
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"Welcome! Here is your onboarding checklist for the first week. Mark each as you complete it."}},
                {"type": "divider"}
            ]
            for idx, item in enumerate(checklist):
                canvas_blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f":white_large_square: {item}"},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Mark as done"},
                        "action_id": f"canvas_checklist_done_{idx}",
                        "value": str(idx)
                    }
                })
            client.chat_postMessage(
                channel=dm_channel,
                blocks=canvas_blocks,
                text=f"{team_name} Onboarding Canvas"
            )
            user_state[user_id] = {"canvas_checklist": [False]*len(checklist), "team": team_name, "checklist_items": checklist}

for idx in range(10):  # Support up to 10 checklist items per team
    def make_canvas_checklist_handler(idx):
        def handler(ack, body, client, idx=idx):
            ack()
            user_id = body["user"]["id"]
            state = user_state.get(user_id, {})
            checklist = state.get("checklist_items", DEFAULT_CHECKLIST)
            if user_id in user_state and "canvas_checklist" in user_state[user_id]:
                user_state[user_id]["canvas_checklist"][idx] = True
            canvas_blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": f"📝 {state.get('team', 'Onboarding')} Onboarding Canvas"}},
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": "Welcome! Here is your onboarding checklist for the first week. Mark each as you complete it."}},
                {"type": "divider"}
            ]
            for i, item in enumerate(checklist):
                checked = user_state[user_id]["canvas_checklist"][i]
                status = ":white_check_mark:" if checked else ":white_large_square:"
                canvas_blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"{status} {item}"},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Mark as done" if not checked else "Done!"},
                        "action_id": f"canvas_checklist_done_{i}",
                        "value": str(i),
                        "style": "primary" if not checked else "default",
                        "disabled": checked
                    }
                })
            dm_channel = get_dm_channel_id(client, user_id)
            client.chat_postMessage(
                channel=dm_channel,
                blocks=canvas_blocks,
                text=f"Updated {state.get('team', 'Onboarding')} Onboarding Canvas."
            )
        return handler
    app.action(f"canvas_checklist_done_{idx}")(make_canvas_checklist_handler(idx))

# Example: Call this at startup or from a command to send the button to the admin
# send_sync_button_to_admin(app.client)

#suggest online resources
def suggest_resources(summary: str, resources_data: dict) -> list:
    matched = []
    summary_lower = summary.lower()
    
    for keyword, url in resources_data.items():
        if keyword.lower() in summary_lower:
            matched.append(f"{keyword}: {url}")
    
    return matched




if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start() 