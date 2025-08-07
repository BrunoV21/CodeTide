try:
    from aicore.config import Config
    from aicore.llm import Llm, LlmConfig
    from chainlit.input_widget import Slider, TextInput, Switch
      
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' and 'chainlit' packages. "
        "Install it with: pip install codetide[agents-ui]"
    ) from e

from codetide.agents.tide.defaults import DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
from codetide.agents.tide.agent import AgentTide
from codetide.mcp.utils import initCodeTide

from typing import Optional
from pathlib import Path
import os

class AgentTideUi(object):
    def __init__(self, project_path: Path = Path("./"), history :Optional[list]=None, llm_config :Optional[LlmConfig]=None):
        self.project_path: Path = Path(project_path)
        self.config_path = os.getenv("AGENT_TIDE_CONFIG_PATH", DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH)
        if llm_config is None:
            config = Config.from_yaml(self.project_path / self.config_path)
            self.llm_config: LlmConfig = config.llm
        else:
            self.llm_config = llm_config
        
        self.agent_tide: AgentTide = None
        self.history = [] if history is None else history
        self.current_step :Optional[int] = None

    async def load(self):
        self.agent_tide = AgentTide(
            llm=Llm.from_config(self.llm_config),
            tide=await initCodeTide(workspace=self.project_path),
            history=self.history
        )

    def increment_step(self)->bool:
        steps = self.agent_tide.steps.root
        if steps:
            if self.current_step is None:
                self.current_step = 0
                return

            self.current_step += 1
            if self.current_step == len(steps):
                self.current_step = None
                self.agent_tide.steps = None
                return True

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
            Switch(
                id="planning_mode",
                label="Planning Mode",
                initial=False,
                description="if active, Agent Tide will first generate a list of tasks and prompt you to select which ones to tackle"
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
    