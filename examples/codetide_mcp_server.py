from codetide.mcp import codeTideMCPServer
from dotenv import load_dotenv

async def main():
    """
    Make sure to set `CODETIDE_WORKSPACE` env var
    """
    tools = await codeTideMCPServer.get_tools()
    print(tools)

if __name__ == "__main__":
    import asyncio
    load_dotenv()
    asyncio.run(main())