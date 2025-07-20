"""
Install the agents version with pip install codetide[agents]
"""

from codetide.mcp.utils import initCodeTide
from codetide.agents.tide import AgentTide
from aicore.llm import Llm, LlmConfig
import os

def init_llm()->Llm:
    llm = Llm.from_config(
        LlmConfig(
            # model="deepseek-chat",
            # provider="deepseek",
            # api_key=os.getenv("DEEPSEEK-API-KEY")
            model="gpt-4.1",
            provider="openai",
            api_key=os.getenv("OPENAI-API-KEY"),
            temperature=0,
        )
    )
    return llm

async def main():
    llm = init_llm()
    tide = await initCodeTide()

    tide = AgentTide(llm=llm, tide=tide)
    await tide.run()

if __name__ == "__main__":
    from dotenv import load_dotenv
    import asyncio
    
    load_dotenv()
    asyncio.run(main())