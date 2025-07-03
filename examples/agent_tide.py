"""
install aicore - pip install core-for-ai
Make sure to set `CODETIDE_WORKSPACE` env var which will be requried for the MCP server to work
"""

from codetide.mcp.agent_tide_system import AGENT_TIDE_SYSTEM_PROMPT
from codetide.mcp import codeTideMCPServer
from aicore.llm import Llm, LlmConfig
from aicore.logger import _logger
from typing import Optional
import keyboard
import os

AGENT_TIDE_ASCII_ART = """

█████╗  ██████╗ ███████╗███╗   ██╗████████╗    ████████╗██╗██████╗ ███████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝    ╚══██╔══╝██║██╔══██╗██╔════╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║          ██║   ██║██║  ██║█████╗  
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║          ██║   ██║██║  ██║██╔══╝  
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║          ██║   ██║██████╔╝███████╗
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝          ╚═╝   ╚═╝╚═════╝ ╚══════╝

"""

def init_llm()->Llm:
    llm = Llm.from_config(
        LlmConfig(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
            api_key=os.getenv("DEEPSEEK-API-KEY")
        )
    )
    
    llm.provider.mcp.add_server(name=codeTideMCPServer.name, parameters=codeTideMCPServer)
    return llm

def trim_messages(messages, tokenizer_fn, max_tokens :Optional[int]=None):
    max_tokens = max_tokens or int(os.environ.get("MAX_HISTORY_TOKENS", 1028))
    while messages and sum(len(tokenizer_fn(msg)) for msg in messages) > max_tokens:
        messages.pop(0)  # Remove from the beginning

async def main(max_tokens :int=48000):
    llm = init_llm()
    history = []

    _logger.logger.info(F"\n{AGENT_TIDE_ASCII_ART}\nReady to surf. Press ESC to exit.\n")
    try:
        while True:
            try:
                message = input("You: ").strip()
                if not message:
                    continue

                if keyboard.is_pressed('esc'):
                    _logger.warning("Escape key pressed — exiting...")
                    break

            except EOFError:
                break
             
            except KeyboardInterrupt:
                _logger.logger.warning("\nExiting...")
                break

            history.append(message)
            trim_messages(history, llm.tokenizer, max_tokens)

            response = await llm.acomplete(history, system_prompt=[AGENT_TIDE_SYSTEM_PROMPT])
            history.append(response)
            
    except KeyboardInterrupt:
        _logger.logger.warning("\nExited by user.")

if __name__ == "__main__": 
    from dotenv import load_dotenv
    import asyncio

    load_dotenv()
    asyncio.run(main())
