import asyncio
import os
from http.client import responses

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from mcp_use import MCPAgent, MCPClient

async def run_memory_chat():
    # Load environment variables
    load_dotenv()

    # Create MCPClient from config file
    os.environ["GROQ_API_KEY"]=os.getenv("GROQ_API_KEY")
    config_file = "browser_mcp.json"

    print("Initilizating chat.........")
    # Create LLM
    client = MCPClient.from_config_file(config_file)
    llm =  ChatGroq(model="qwen-qwq-32b")

    agent = MCPAgent(
        llm=llm,
        client=client,
        max_steps=15,
        memory_enabled=True
    )

    print("Interactive MCP Chat")


    try:
        while True:
            user_input = input("\nYou ")

            if user_input.lower() in ["exit", "quit"]:
                print("Ending convo...")
                break

            if user_input.lower() in ["clear"]:
                print("clearing convo...")
                continue


            print("\n Assistant: ", end="", flush=True)

            try:
                response = await agent.run(user_input)
                print(response)

            except Exception as e:
                print(f"\n Error: {e}")

    finally:
        if client and client.sessions:
            await client.close_all_sessions()

if __name__ == "__main__":
    asyncio.run(run_memory_chat())