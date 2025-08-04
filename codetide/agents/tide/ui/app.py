# ruff: noqa: E402
from pathlib import Path
import os

os.environ.setdefault("CHAINLIT_APP_ROOT", str(Path(os.path.abspath(__file__)).parent))
os.environ.setdefault("CHAINLIT_AUTH_SECRET","@6c1HFdtsjiYKe,-t?dZXnq%4xrgS/YaHte/:Dr6uYq0su/:fGX~M2uy0.ACehaK")

try:
    from aicore.config import Config
    from aicore.llm import Llm, LlmConfig
    from aicore.logger import _logger
    from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN#, REASONING_START_TOKEN, REASONING_STOP_TOKEN
    from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
    from chainlit.input_widget import Slider, TextInput
    from chainlit.types import ThreadDict
    from chainlit.cli import run_chainlit
    import chainlit as cl
      
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' and 'chainlit' packages. "
        "Install it with: pip install codetide[agents-ui]"
    ) from e

from codetide.agents.data_layer import init_db
from codetide.agents.tide.defaults import DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
from codetide.agents.tide.agent import AgentTide
from codetide.mcp.utils import initCodeTide

from typing import List, Optional, Tuple
import argparse
import asyncio
import orjson

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
    
def process_thread(thread :ThreadDict)->Tuple[List[dict], Optional[LlmConfig]]:
    ### type: tool
    ### if nout ouput pop
    ### start = end
    idx_to_pop = []
    
    for i, entry in enumerate(thread.get("steps")):

        if entry.get("type") == "tool":
            if not entry.get("output"):
                idx_to_pop.insert(0, i)
                continue

            entry["start"] = entry["end"]

    for idx in idx_to_pop:
        thread.get("steps").pop(idx)

    metadata = thread.get("metadata")
    if metadata:
        metadata = orjson.loads(metadata)
        history = metadata.get("chat_history", [])
        settings = metadata.get("chat_settings")
    
    else:
        history = []
        settings = None

    return history, settings

@cl.password_auth_callback
def auth():
    return cl.User(identifier="test")

@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=f"sqlite+aiosqlite:///{os.environ['CHAINLIT_APP_ROOT']}/database.db")

@cl.on_settings_update
async def setup_llm_config(settings):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    settings = await cl.ChatSettings(agent_tide_ui.settings()).send()
    
    agent_tide_ui.llm_config = LlmConfig(**settings)
    if Path(settings.get("project_path")) != agent_tide_ui.project_path:
        agent_tide_ui.project_path = settings.get("project_path")
        await agent_tide_ui.load()
    else:
        agent_tide_ui.agent_tide.llm = Llm.from_config(agent_tide_ui.llm_config)

@cl.on_chat_start
async def start_chat():
    agent_tide_ui = AgentTideUi(os.getenv("AGENT_TIDE_PROJECT_PATH", "./"))
    await agent_tide_ui.load()
    cl.user_session.set("AgentTideUi", agent_tide_ui)
    await cl.ChatSettings(agent_tide_ui.settings()).send()
    
    cl.user_session.set("chat_history", [])

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    history, settings = process_thread(thread)
    agent_tide_ui = AgentTideUi(os.getenv("AGENT_TIDE_PROJECT_PATH", "./"), history=history, llm_config=settings)
    await agent_tide_ui.load()
    cl.user_session.set("AgentTideUi", agent_tide_ui)

async def run_concurrent_tasks(agent_tide_ui: AgentTideUi):
    asyncio.create_task(agent_tide_ui.agent_tide.agent_loop())
    asyncio.create_task(_logger.distribute())
    while True:
        async for chunk in _logger.get_session_logs(agent_tide_ui.agent_tide.llm.session_id):
            yield chunk
            
@cl.on_message
async def agent_loop(message: cl.Message):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    
    # Note: by default, the list of messages is saved and the entire user session is saved in the thread metadata
    chat_history = cl.user_session.get("chat_history")
    

    chat_history.append({"role": "user", "content": message.content})
    await agent_tide_ui.add_to_history(message.content)
    msg = cl.Message(content="")
    buffer = ""
    in_patch_block = False
    begin_marker = "*** Begin Patch"
    end_marker = "*** End Patch"
    
    async with cl.Step("ApplyPatch", type="tool") as diff_step:
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
        
        chat_history.append({"role": "assistant", "content": msg.content})
        await agent_tide_ui.add_to_history(msg.content)

def serve(
    host=None,
    port=None,
    root_path=None,
    ssl_certfile=None,
    ssl_keyfile=None,
    ws_per_message_deflate="true",
    ws_protocol="auto"
):
    if host is not None:
        os.environ["CHAINLIT_HOST"] = str(host)
    if port is not None:
        os.environ["CHAINLIT_PORT"] = str(port)
    if root_path is not None:
        os.environ["CHAINLIT_ROOT_PATH"] = str(root_path)
    if ssl_certfile is not None:
        os.environ["CHAINLIT_SSL_CERT"] = str(ssl_certfile)
    if ssl_keyfile is not None:
        os.environ["CHAINLIT_SSL_KEY"] = str(ssl_keyfile)
    if ws_per_message_deflate is not None:
        os.environ["UVICORN_WS_PER_MESSAGE_DEFLATE"] = str(ws_per_message_deflate)
    if ws_protocol is not None:
        os.environ["UVICORN_WS_PROTOCOL"] = str(ws_protocol)
    run_chainlit(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description="Launch the Tide UI server.")
    parser.add_argument("--host", type=str, default=None, help="Host to bind to")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to")
    parser.add_argument("--root-path", type=str, default=None, help="Root path for the app")
    parser.add_argument("--ssl-certfile", type=str, default=None, help="Path to SSL certificate file")
    parser.add_argument("--ssl-keyfile", type=str, default=None, help="Path to SSL key file")
    parser.add_argument("--ws-per-message-deflate", type=str, default="true", help="WebSocket per-message deflate (true/false)")
    parser.add_argument("--ws-protocol", type=str, default="auto", help="WebSocket protocol")
    parser.add_argument("--project-path", type=str, default="./", help="Path to the project directory")
    parser.add_argument("--config-path", type=str, default=DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH, help="Path to the config file")
    args = parser.parse_args()

    os.environ["AGENT_TIDE_PROJECT_PATH"] = args.project_path
    os.environ["AGENT_TIDE_CONFIG_PATH"] = args.config_path

    asyncio.run(init_db(f"{os.environ['CHAINLIT_APP_ROOT']}/database.db"))

    serve(
        host=args.host,
        port=args.port,
        root_path=args.root_path,
        ssl_certfile=args.ssl_certfile,
        ssl_keyfile=args.ssl_keyfile,
        ws_per_message_deflate=args.ws_per_message_deflate,
        ws_protocol=args.ws_protocol,
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db(f"{os.environ['CHAINLIT_APP_ROOT']}/database.db"))
    serve()