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
    buffer = ""
    in_patch_block = False
    begin_marker = "*** Begin Patch"
    end_marker = "*** End Patch"
    
    async with cl.Step("ApplyPath", type="tool") as diff_step:
        await diff_step.remove()
        async for chunk in run_concurrent_tasks(agent_tide_ui):
            if chunk == STREAM_START_TOKEN:
                continue
            if chunk == STREAM_END_TOKEN:
                break
            
            buffer += chunk
            
            # Process buffer until no more complete markers can be found
            while True:
                if not in_patch_block:
                    idx = buffer.find(begin_marker)
                    if idx == -1:
                        # No begin marker found, stream everything except what might be a partial marker
                        # Keep potential partial marker at end
                        if len(buffer) >= len(begin_marker):
                            stream_content = buffer[:-len(begin_marker)+1]
                            if stream_content:
                                await msg.stream_token(stream_content)
                            buffer = buffer[-len(begin_marker)+1:]
                        break
                    else:
                        if idx > 0:
                            # Stream content before the marker to msg
                            await msg.stream_token(buffer[:idx])
                        
                        # Start the code block in diff_step
                        await diff_step.stream_token("\n```shell\n")
                        in_patch_block = True
                        
                        # Remove everything up to and including the begin marker + newline
                        buffer = buffer[idx + len(begin_marker):]
                        if buffer.startswith('\n'):
                            buffer = buffer[1:]
                        # Continue processing the buffer
                else:
                    # We're in a patch block
                    idx = buffer.find(end_marker)
                    if idx == -1:
                        # No end marker found, stream everything except what might be a partial marker
                        if len(buffer) >= len(end_marker):
                            stream_content = buffer[:-len(end_marker)+1]
                            if stream_content:
                                await diff_step.stream_token(stream_content)
                            buffer = buffer[-len(end_marker)+1:]
                        break
                    else:
                        # Found end marker
                        if idx > 0:
                            # Stream content before the end marker to diff_step
                            await diff_step.stream_token(buffer[:idx])
                        
                        # Close the code block in diff_step
                        await diff_step.stream_token("\n```\n")
                        in_patch_block = False
                        
                        # Remove everything up to and including the end marker
                        buffer = buffer[idx + len(end_marker):]
                        if buffer.startswith('\n'):
                            buffer = buffer[1:]
                        # Continue processing the buffer (might find another patch!)

        # Handle any remaining content in buffer
        if buffer:
            if in_patch_block:
                await diff_step.stream_token(buffer)
                await diff_step.stream_token("\n```\n")  # Close any open code block
            else:
                await msg.stream_token(buffer)

        # Send the final message
        await msg.send()
        await agent_tide_ui.add_to_history(msg.content)

def serve():
    run_chainlit(os.path.abspath(__file__))