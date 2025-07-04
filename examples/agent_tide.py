"""
install aicore - pip install core-for-ai
Make sure to set `CODETIDE_WORKSPACE` env var which will be requried for the MCP server to work
"""

from codetide.mcp.agent_tide_system import AGENT_TIDE_SYSTEM_PROMPT
from codetide.mcp import codeTideMCPServer
from aicore.llm import Llm, LlmConfig
from aicore.logger import _logger

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import PromptSession
from typing import Optional
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

async def main(max_tokens: int = 48000):
    llm = init_llm()
    history = []

    # 1. Set up key bindings
    bindings = KeyBindings()

    @bindings.add('escape')
    def _(event):
        """When Esc is pressed, exit the application."""
        _logger.logger.warning("Escape key pressed — exiting...")
        event.app.exit()

    # 2. Create a prompt session with the custom key bindings
    session = PromptSession(key_bindings=bindings)

    _logger.logger.info(f"\n{AGENT_TIDE_ASCII_ART}\nReady to surf. Press ESC to exit.\n")
    try:
        while True:
            try:
                # 3. Use the async prompt instead of input()
                message = await session.prompt_async("You: ")
                message = message.strip()

                if not message:
                    continue

            except (EOFError, KeyboardInterrupt):
                # prompt_toolkit raises EOFError on Ctrl-D and KeyboardInterrupt on Ctrl-C
                _logger.warning("\nExiting...")
                break

            history.append(message)
            trim_messages(history, llm.tokenizer, max_tokens)

            print("Agent: Thinking...")
            response = await llm.acomplete(history, system_prompt=[AGENT_TIDE_SYSTEM_PROMPT], as_message_records=True)
            print(f"Agent: {response}")
            history.extend(response)

    except asyncio.CancelledError:
        # This can happen if the event loop is shut down
        pass
    finally:
        _logger.logger.info("\nExited by user. Goodbye!")

if __name__ == "__main__": 
    from dotenv import load_dotenv
    import asyncio

    load_dotenv()
    asyncio.run(main())
