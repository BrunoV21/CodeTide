
from pathlib import Path
import argparse
import asyncio

from ...mcp.utils import initCodeTide
from .cli_step import init_llm, DEFAULT_MAX_HISTORY_TOKENS
from .agent import AgentTide

def main():
    parser = argparse.ArgumentParser(description="AgentTide Full Terminal CLI")
    parser.add_argument(
        "--project_path",
        type=str,
        default=".",
        help="Path to the project root (default: current directory)"
    )
    parser.add_argument(
        "--max_history_tokens",
        type=int,
        default=DEFAULT_MAX_HISTORY_TOKENS,
        help=f"Maximum number of tokens to keep in history (default: {DEFAULT_MAX_HISTORY_TOKENS})"
    )
    args = parser.parse_args()

    asyncio.run(run_agent_tide_cli(args.project_path, args.max_history_tokens))

async def run_agent_tide_cli(project_path: str, max_history_tokens: int):
    project_path = Path(project_path)
    llm = init_llm(project_path)
    tide = await initCodeTide(workspace=project_path)
    agent = AgentTide(
        llm=llm,
        tide=tide,
        history=[]
    )
    await agent.run(max_tokens=max_history_tokens)

if __name__ == "__main__":
    main()
