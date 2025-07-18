# from .agent_tide_system import AGENT_TIDE_SYSTEM_PROMPT
from fastmcp import FastMCP

codeTideMCPServer = FastMCP(
    name="CodeTide",
    # instructions=AGENT_TIDE_SYSTEM_PROMPT,
)
