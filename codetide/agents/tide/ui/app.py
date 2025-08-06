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
    from codetide.agents.tide.ui.stream_processor import StreamProcessor, MarkerConfig
    from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
    from chainlit.input_widget import Slider, TextInput, Switch
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
import getpass
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
    
def process_thread(thread :ThreadDict)->Tuple[List[dict], Optional[LlmConfig]]:
    ### type: tool
    ### if nout ouput pop
    ### start = end
    idx_to_pop = []
    steps = thread.get("steps")
    tool_moves = []
    for i, entry in enumerate(steps):
        if entry.get("type") == "tool":
            if not entry.get("output"):
                idx_to_pop.insert(0, i)
                continue
            entry["start"] = entry["end"]
            tool_moves.append(i)

    for idx in idx_to_pop:
        steps.pop(idx)

    # Move tool entries with output after the next non-tool entry
    # Recompute tool_moves since popping may have changed indices
    # We'll process from the end to avoid index shifting issues
    # First, collect the indices of tool entries with output again
    tool_indices = []
    for i, entry in enumerate(steps):
        if entry.get("type") == "tool" and entry.get("output"):
            tool_indices.append(i)
    # For each tool entry, move it after the next non-tool entry
    # Process from last to first to avoid index shifting
    for tool_idx in reversed(tool_indices):
        tool_entry = steps[tool_idx]
        # Find the next non-tool entry after tool_idx
        insert_idx = None
        for j in range(tool_idx + 1, len(steps)):
            if steps[j].get("type") != "tool":
                insert_idx = j + 1
                break
        if insert_idx is not None and insert_idx - 1 != tool_idx:
            # Remove and insert at new position
            steps.pop(tool_idx)
            # If tool_idx < insert_idx, after pop, insert_idx decreases by 1
            if tool_idx < insert_idx:
                insert_idx -= 1
            steps.insert(insert_idx, tool_entry)

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
    username = getpass.getuser()
    return cl.User(identifier=username, display_name=username)

@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=f"sqlite+aiosqlite:///{os.environ['CHAINLIT_APP_ROOT']}/database.db")

@cl.on_settings_update
async def setup_llm_config(settings):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    settings = await cl.ChatSettings(agent_tide_ui.settings()).send()
    
    agent_tide_ui.llm_config = LlmConfig(**settings)
    if Path(settings.get("project_path")) != agent_tide_ui.project_path:
        agent_tide_ui.project_path = Path(settings.get("project_path"))
        await agent_tide_ui.load()
        await cl.send_window_message(f"Agent Tide is connected to workspace: {settings.get('project_path')}")
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
    asyncio.create_task(agent_tide_ui.agent_tide.agent_loop_planing())
    asyncio.create_task(_logger.distribute())
    while True:
        async for chunk in _logger.get_session_logs(agent_tide_ui.agent_tide.llm.session_id):
            yield chunk

@cl.on_message
async def agent_loop(message: cl.Message):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    chat_history = cl.user_session.get("chat_history")
    
    chat_history.append({"role": "user", "content": message.content})
    await agent_tide_ui.add_to_history(message.content)
    
    msg = cl.Message(content="")
    
    async with cl.Step("ApplyPatch", type="tool") as diff_step:
        await diff_step.remove()
        
        # Initialize the stream processor
        stream_processor = StreamProcessor(
            marker_configs=[
                MarkerConfig(
                    begin_marker="*** Begin Patch",
                    end_marker="*** End Patch", 
                    start_wrapper="\n```shell\n",
                    end_wrapper="\n```\n",
                    target_step=diff_step
                ),
                MarkerConfig(
                    begin_marker="*** Begin Steps",
                    end_marker="*** End Steps", 
                    start_wrapper="\n```shell\n",
                    end_wrapper="\n```\n",
                    target_step=msg
                ) 
            ],
            global_fallback_msg=msg
        )
        
        async for chunk in run_concurrent_tasks(agent_tide_ui):
            if chunk == STREAM_START_TOKEN:
                continue

            if chunk == STREAM_END_TOKEN:
                 #  Handle any remaining content
                await stream_processor.finalize()
                break
            
            await stream_processor.process_chunk(chunk)
        
        # print(f"{agent_tide_ui.agent_tide.steps=}")
        if agent_tide_ui.agent_tide.steps: 
            msg.actions = [
                cl.Action(name="execute_steps", payload={"value": "example_value"}, label="Run Steps One by One")
            ]

        # # Send the final message
        await msg.send()
        
        chat_history.append({"role": "assistant", "content": msg.content})
        await agent_tide_ui.add_to_history(msg.content)

# def generate_temp_password(length=16):
#     characters = string.ascii_letters + string.digits + string.punctuation
#     return ''.join(secrets.choice(characters) for _ in range(length))

def serve(
    host=None,
    port=None,
    root_path=None,
    ssl_certfile=None,
    ssl_keyfile=None,
    ws_per_message_deflate="true",
    ws_protocol="auto"
):    
    username = getpass.getuser()    
    GREEN = "\033[92m"
    RESET = "\033[0m"

    print(f"\n{GREEN}Your chainlit username is `{username}`{RESET}\n")


    # if not os.getenv("_PASSWORD"):
    #     temp_password = generate_temp_password()
    #     os.environ["_PASSWORD"] = temp_password
    #     print(f"Your temporary password is `{temp_password}`")

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
    # TODO add logic in the apply patch path calling to ensure a correct file path is always used