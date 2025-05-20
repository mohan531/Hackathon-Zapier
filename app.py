import os
import asyncio
from dotenv import load_dotenv
from pprint import pprint

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

# Read environment variables
ZAPIER_MCP_URL = os.getenv("ZAPIER_MCP_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#general")
SLACK_MESSAGE = os.getenv("SLACK_MESSAGE", "Hello from LangChain MCP adapter!")

# Async main function
async def main():
    # Initialize MultiServerMCPClient (no async with here)
    client = MultiServerMCPClient({
        "zapier": {
            "url": ZAPIER_MCP_URL,
            "transport": "sse"
        }
    })
    

    # Use session with the "zapier" server
    async with client.session("zapier") as session:

        tools = await session.list_tools()
        # Initialize Gemini model
        model =  ChatGroq(model="qwen-qwq-32b")

        # Create agent
        agent = create_react_agent(model, tools)

        # Prepare agent input
        agent_input = {
            "messages": [
                {
                    "role": "user",
                    "content": f'Please post the message "{SLACK_MESSAGE}" to the {SLACK_CHANNEL} Slack channel.'
                }
            ]
        }

        print("\n🤖 Invoking LangGraph agent...")
        agent_result = await agent.ainvoke(agent_input)

        # Parse agent response
        final_message = agent_result.get("final_answer") or agent_result.get("output")

        if final_message:
            print("\n✅ Agent output:", final_message)
        else:
            for msg in reversed(agent_result.get("messages", [])):
                if msg.get("type") == "ai" and msg.get("content"):
                    print("\n✅ Agent said:", msg["content"])
                    break
            else:
                print("⚠️ No AI output found in agent result.")

# Entrypoint
if __name__ == "__main__":
    asyncio.run(main())