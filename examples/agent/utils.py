"""
install aicore - pip install core-for-ai
Make sure to set `CODETIDE_WORKSPACE` env var which will be requried for the MCP server to work
"""

from codetide.mcp import codeTideMCPServer
from aicore.llm import Llm, LlmConfig

from typing import Optional
import os




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
    while messages and sum(len(tokenizer_fn(str(msg))) for msg in messages) > max_tokens:
        messages.pop(0)  # Remove from the beginning