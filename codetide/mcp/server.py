# from .agent_tide_system import AGENT_TIDE_SYSTEM_PROMPT
from fastmcp import FastMCP

codeTideMCPServer = FastMCP(
    name="codetide",
    # instructions=AGENT_TIDE_SYSTEM_PROMPT,
)

def serve():
    codeTideMCPServer.run("stdio")

async def aserve():
    await codeTideMCPServer.run_stdio_async()

if __name__ == "__main__":
    import asyncio
    asyncio.run(serve())