try:
    from aicore.config import Config
    from aicore.llm import Llm, LlmConfig
    from chainlit.input_widget import Slider, TextInput
      
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' and 'chainlit' packages. "
        "Install it with: pip install codetide[agents-ui]"
    ) from e

from codetide.agents.tide.prompts import CMD_CODE_REVIEW_PROMPT, CMD_COMMIT_PROMPT, CMD_WRITE_TESTS_PROMPT
from codetide.agents.tide.defaults import DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
from codetide.agents.tide.ui.defaults import PLACEHOLDER_LLM_CONFIG
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
            try:
                config = Config.from_yaml(self.project_path / self.config_path)
                self.llm_config: LlmConfig = config.llm
            except Exception:
                self.llm_config = LlmConfig(**PLACEHOLDER_LLM_CONFIG)

        else:
            self.llm_config = llm_config
        
        self.agent_tide: AgentTide = None
        self.history = [] if history is None else history
        self.current_step :Optional[int] = None
        self.commands_prompts = {
            "review": CMD_CODE_REVIEW_PROMPT,
            "test": CMD_WRITE_TESTS_PROMPT,
            "commit": CMD_COMMIT_PROMPT
        }
    
    commands = [
        {"id": "review", "icon": "search-check", "description": "Review file(s) or object(s)"},
        {"id": "test", "icon": "flask-conical", "description": "Test file(s) or object(s)"},
        {"id": "commit", "icon": "git-commit", "description": "Generate commit message"},
    ]

    async def load(self):
        llm = Llm.from_config(self.llm_config)
        self.agent_tide = AgentTide(
            llm=llm,
            tide=await initCodeTide(workspace=self.project_path),
            history=self.history
        )
        self.agent_tide.llm.session_id = self.agent_tide.session_id

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
    
    def get_command_prompt(self, command :str)->Optional[str]:
       return self.commands_prompts.get(command)
