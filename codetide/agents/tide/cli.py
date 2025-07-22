from ...mcp.utils import initCodeTide
from . import AgentTide


try:
    from aicore.logger import _logger
    from aicore.config import Config
    from aicore.llm import Llm
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' package. "
        "Install it with: pip install codetide[agents]"
    ) from e

from pathlib import Path
import os

DEFAULT_AGENT_TIDE_LLM_CONFIG = "./config/agent_tide_llm_config.yml"
DEFAULT_MAX_TOKENS = 48000

def init_llm(project_path :Path)->Llm:
    # TODO change this to from default path
    config_path = os.getenv("AGENT_TIDE_CONFIG_PATH", DEFAULT_AGENT_TIDE_LLM_CONFIG)
    llm = Llm.from_config(Config.from_yaml(project_path / config_path).llm)
    return llm

async def run_tide_step(project_path :str, history :list):
    if not history:
        return

    project_path = Path(project_path)
    _logger.logger.remove()

    llm = init_llm(project_path)
    tide = await initCodeTide(workspace=project_path)

    aTide = AgentTide(
        llm=llm,
        tide=tide,
        history=history
    )
    aTide.trim_messages(aTide.history, llm.tokenizer, os.getenv("AGENT_TIDE_MAX_HISTORY_TOKENS", DEFAULT_MAX_TOKENS))

    await aTide.agent_loop()


def parse_history_arg(history_arg):
    import json
    import os
    if not history_arg:
        return []
    if os.path.isfile(history_arg):
        with open(history_arg, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        return json.loads(history_arg)
    except Exception:
        return [history_arg]


def main():
    import argparse
    import asyncio
    parser = argparse.ArgumentParser(description="AgentTide Step CLI")
    parser.add_argument("project_path", help="Path to the project root")
    parser.add_argument("history", nargs="?", default=None, help="History as JSON string, file path, or single message")
    args = parser.parse_args()
    history = parse_history_arg(args.history)
    asyncio.run(run_tide_step(args.project_path, history))