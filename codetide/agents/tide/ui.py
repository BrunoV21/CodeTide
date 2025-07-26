try:
    from aicore.config import Config
    from aicore.llm import Llm, LlmConfig
    from aicore.logger import _logger
    from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN#, REASONING_START_TOKEN, REASONING_STOP_TOKEN
    import chainlit as cl
    from chainlit.cli import run_chainlit
    from chainlit.input_widget import Slider, TextInput
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' and 'chainlit' packages. "
        "Install it with: pip install codetide[agents-ui]"
    ) from e

from codetide.agents.tide.defaults import DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
from codetide.agents.tide.agent import AgentTide
from codetide.mcp.utils import initCodeTide

from pathlib import Path
import asyncio
import os

class AgentTideUi(object):
    def __init__(self, project_path: Path = Path("./")):
        self.project_path: Path = Path(project_path)
        self.config_path = os.getenv("AGENT_TIDE_CONFIG_PATH", DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH)
        config = Config.from_yaml(self.project_path / self.config_path)
        self.llm_config: LlmConfig = config.llm
        self.agent_tide: AgentTide = None
        self.history = []

    async def load(self):
        self.agent_tide = AgentTide(
            llm=Llm.from_config(self.llm_config),
            tide=await initCodeTide(workspace=self.project_path),
            history=self.history
        )

    async def add_to_history(self, message):
        self.history.append(message)
        if not self.agent_tide:
            await self.load()
        else:
            self.agent_tide.history.append(message)

    def settings(self):
        return [
            TextInput(
                id="project_path",
                label="Project Path",
                initial=str(Path(os.getcwd())/(self.project_path))
            ),
            TextInput(
                id="provider",
                label="Provider",
                initial=self.llm_config.provider
            ),
            TextInput(
                id="model",
                label="LLM",
                initial=self.llm_config.model
            ),
            TextInput(
                id="api_key",
                label="API Key",
                initial=self.llm_config.api_key
            ),
            TextInput(
                id="base_url",
                label="Base URL",
                initial=self.llm_config.base_url
            ),
            Slider(
                id="temperature",
                label="Temperature",
                initial=self.llm_config.temperature,
                min=0,
                max=1,
                step=0.1,
            ),
            Slider(
                id="max_tokens",
                label="Max Tokens",
                initial=self.llm_config.max_tokens,
                min=4096,
                max=self.llm_config.max_tokens,
                step=4096,
            )
        ]

@cl.on_settings_update
async def setup_llm_config(settings):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    await cl.ChatSettings(agent_tide_ui.settings()).send()
    agent_tide_ui.llm = Llm.from_config(agent_tide_ui.llm_config)

@cl.on_chat_start
async def start_chat():
    agent_tide_ui = AgentTideUi(os.getenv("AGENT_TIDE_PROJECT_PATH", "./"))
    await agent_tide_ui.load()
    cl.user_session.set("AgentTideUi", agent_tide_ui)
    await cl.ChatSettings(agent_tide_ui.settings()).send()

async def run_concurrent_tasks(agent_tide_ui: AgentTideUi):
    asyncio.create_task(agent_tide_ui.agent_tide.agent_loop())
    asyncio.create_task(_logger.distribute())
    while True:
        async for chunk in _logger.get_session_logs(agent_tide_ui.agent_tide.llm.session_id):
            yield chunk
            
@cl.on_message
async def main(message: cl.Message):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    await agent_tide_ui.add_to_history(message.content)
    msg = cl.Message(content="")
    async for chunk in run_concurrent_tasks(agent_tide_ui):
        if chunk == STREAM_START_TOKEN:
            continue
        if chunk == STREAM_END_TOKEN:
            break
        await msg.stream_token(chunk)
    await agent_tide_ui.add_to_history(msg.content)
    await msg.send()

def serve():
    run_chainlit(os.path.abspath(__file__))