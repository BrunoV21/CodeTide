"""
install aicore - pip install core-for-ai
Make sure to set `CODETIDE_WORKSPACE` env var which will be requried for the MCP server to work
"""

from aicore.llm import Llm, LlmConfig
from codetide.mcp import codeTideMCPServer
import os

async def main():
    llm = Llm.from_config(
        LlmConfig(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
            api_key=os.getenv("DEEPSEEK-API-KEY")
        )
    )
    
    llm.provider.mcp.add_server(name=codeTideMCPServer.name, parameters=codeTideMCPServer)
    await llm.acomplete(
        prompt="How many parsers are currently supported?",
        system_prompt=["You are a software engineer with tool calling capabilities who will help the user navigate his codebase"],
        agent_id="agent-tide",
        action_id="warm-up"
    )

if __name__ == "__main__": 
    from dotenv import load_dotenv
    import asyncio

    load_dotenv()
    asyncio.run(main())


