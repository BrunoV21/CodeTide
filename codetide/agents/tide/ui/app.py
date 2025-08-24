# ruff: noqa: E402
from pathlib import Path
import os

os.environ.setdefault("CHAINLIT_APP_ROOT", str(Path(os.path.abspath(__file__)).parent))
os.environ.setdefault("CHAINLIT_AUTH_SECRET","@6c1HFdtsjiYKe,-t?dZXnq%4xrgS/YaHte/:Dr6uYq0su/:fGX~M2uy0.ACehaK")

try:
    from aicore.config import Config
    from aicore.llm import Llm, LlmConfig
    from aicore.models import AuthenticationError, ModelError
    from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN#, REASONING_START_TOKEN, REASONING_STOP_TOKEN
    from codetide.agents.tide.ui.stream_processor import StreamProcessor, MarkerConfig
    from codetide.agents.tide.ui.utils import process_thread, run_concurrent_tasks
    from codetide.agents.tide.ui.defaults import AGENT_TIDE_PORT, STARTERS
    from codetide.agents.tide.ui.agent_tide_ui import AgentTideUi
    from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
    from codetide.agents.tide.models import Step
    from chainlit.types import ThreadDict
    from chainlit.cli import run_chainlit
    from typing import Optional
    import chainlit as cl
      
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' and 'chainlit' packages. "
        "Install it with: pip install codetide[agents-ui]"
    ) from e

from codetide.agents.tide.ui.defaults import AICORE_CONFIG_EXAMPLE, EXCEPTION_MESSAGE, MISSING_CONFIG_MESSAGE
from codetide.agents.tide.defaults import DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
from codetide.core.defaults import DEFAULT_ENCODING
from codetide.agents.data_layer import init_db
import argparse
import getpass
import asyncio
import json
import yaml

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

async def validate_llm_config(agent_tide_ui: AgentTideUi):
    exception = True
    while exception:
        try:
            agent_tide_ui.agent_tide.llm.provider.validate_config(force_check_against_provider=True)
            exception = None

        except (AuthenticationError, ModelError) as e:
            exception = e
            await cl.Message(
                content=MISSING_CONFIG_MESSAGE.format(
                    agent_tide_config_path=os.getenv("AGENT_TIDE_CONFIG_PATH", DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH),
                    config_file=Path(os.getenv("AGENT_TIDE_CONFIG_PATH", DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH)).name,
                    example_config=AICORE_CONFIG_EXAMPLE
                ),
                elements=[
                    cl.File(
                        name="config.yml",
                        # path=os.getenv("AGENT_TIDE_CONFIG_PATH", DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH),
                        display="inline",
                        content=AICORE_CONFIG_EXAMPLE,
                        size="small"
                    ),
                ]
            ).send()

            _config_files = None
            while _config_files is None:
                _config_files = await cl.AskFileMessage(
                    content=EXCEPTION_MESSAGE.format(exception=json.dumps(exception.__dict__, indent=4)),
                    accept=[".yml", ".yaml"],
                    timeout=3600
                ).send()

            if _config_files:
                _config_file = _config_files[0]

                try:
                    with open(_config_file.path, "r", encoding=DEFAULT_ENCODING) as _file:
                        config_raw = _file.read()
                        config_dict = yaml.safe_load(config_raw)
                        config = Config(**config_dict)

                    agent_tide_ui.agent_tide.llm = Llm.from_config(config.llm)
                    agent_tide_ui.agent_tide.llm.provider.session_id = agent_tide_ui.agent_tide.session_id

                    config_path = os.getenv("AGENT_TIDE_CONFIG_PATH", DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH)
                    config_dir_path = os.path.split(config_path)[0]
                    if not os.path.exists(config_dir_path):
                        os.makedirs(config_dir_path, exist_ok=True)
                    
                    with open(config_path, "w", encoding=DEFAULT_ENCODING) as _file:
                        _file.write(config_raw)

                except Exception as e:
                    exception = e

@cl.on_chat_start
async def start_chat():
    # TODO think of fast way to initialize and get settings
    # agent_tide_ui = AgentTideUi(os.getenv("AGENT_TIDE_PROJECT_PATH", "./"))
    # await agent_tide_ui.load()
    # cl.user_session.set("AgentTideUi", None)
    # cl.user_session.set("session_id", agent_tide_ui.agent_tide.session_id)
    # await cl.ChatSettings(agent_tide_ui.settings()).send()
    await cl.context.emitter.set_commands(AgentTideUi.commands)
    cl.user_session.set("chat_history", [])

@cl.set_starters
async def set_starters():
    return [cl.Starter(**kwargs) for kwargs in STARTERS]

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    history, settings, session_id = process_thread(thread)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("settings", settings)
    cl.user_session.set("chat_history", history)

async def loadAgentTideUi()->AgentTideUi:
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    print(f"{agent_tide_ui=}")
    if agent_tide_ui is None:
        try:
            agent_tide_ui = AgentTideUi(
                os.getenv("AGENT_TIDE_PROJECT_PATH", "./"),
                history=cl.user_session.get("chat_history"),
                llm_config=cl.user_session.get("settings")
            )
            await agent_tide_ui.load()

        except FileNotFoundError:
            ...

        await validate_llm_config(agent_tide_ui)

        session_id = cl.user_session.get("session_id")
        if session_id:
            agent_tide_ui.agent_tide.llm.provider.session_id = session_id
        else:
            cl.user_session.set("session_id", agent_tide_ui.agent_tide.llm.provider.session_id)

        cl.user_session.set("AgentTideUi", agent_tide_ui)

    return agent_tide_ui

@cl.action_callback("execute_steps")
async def on_execute_steps(action :cl.Action):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")

    latest_step_message :cl.Message = cl.user_session.get("latest_step_message")
    if latest_step_message and latest_step_message.id == action.payload.get("msg_id"):
        await latest_step_message.remove_actions()

    if agent_tide_ui.current_step is None:
        task_list = cl.TaskList("Steps")
        for step in agent_tide_ui.agent_tide.steps.root:
            task = cl.Task(title=step.description)#, forId=message.id)
            await task_list.add_task(task)

        # Update the task list in the interface
        await task_list.send()
        cl.user_session.set("StepsTaskList", task_list)

    else:
        task_list = cl.user_session.get("StepsTaskList")

    is_done = agent_tide_ui.increment_step()
    # Optionally remove the action button from the chatbot user interface

    if is_done:
        task_list.tasks[-1].status = cl.TaskStatus.DONE
        await cl.sleep(3)
        await task_list.remove()
        await action.remove()
        
        # await cl.send_window_message("Finished implementing Steps")

    else:
        current_task_idx = agent_tide_ui.current_step
        if current_task_idx >= 1:
            task_list.tasks[current_task_idx-1].status = cl.TaskStatus.DONE

        step :Step = agent_tide_ui.agent_tide.steps.root[agent_tide_ui.current_step]

        task_list.status = f"Executing step {current_task_idx}"
        await task_list.send()
        await action.remove()
        
        step_instructions_msg = await cl.Message(
            content=step.as_instruction(),
            author="Agent Tide"
        ).send()

        await agent_loop(step_instructions_msg, codeIdentifiers=step.context_identifiers)
        
        task_list.status = f"Waiting feedback on step {current_task_idx}"
        await task_list.send()

@cl.action_callback("stop_steps")
async def on_stop_steps(action :cl.Action):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")

    latest_step_message :cl.Message = cl.user_session.get("latest_step_message")
    if latest_step_message and latest_step_message.id == action.payload.get("msg_id"):
        await latest_step_message.remove_actions()
    
    task_list = cl.user_session.get("StepsTaskList")
    if task_list:
        agent_tide_ui.current_step = None 
        await task_list.remove()
    
        # await cl.send_window_message("Current Steps have beed discarded")


@cl.on_message
async def agent_loop(message: cl.Message, codeIdentifiers: Optional[list] = None):
    agent_tide_ui = await loadAgentTideUi()

    chat_history = cl.user_session.get("chat_history")

    if message.command:
        command_prompt = await agent_tide_ui.get_command_prompt(message.command)
        if command_prompt:
            message.content = "\n\n---\n\n".join([command_prompt, message.content])

    chat_history.append({"role": "user", "content": message.content})
    await agent_tide_ui.add_to_history(message.content)

    msg = cl.Message(content="", author="Agent Tide")

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

        async for chunk in run_concurrent_tasks(agent_tide_ui, codeIdentifiers):
            if chunk == STREAM_START_TOKEN:
                continue

            if chunk == STREAM_END_TOKEN:
                #  Handle any remaining content
                await stream_processor.finalize()
                break

            await stream_processor.process_chunk(chunk)

        if agent_tide_ui.agent_tide.steps:
            cl.user_session.set("latest_step_message", msg)
            msg.actions = [
                cl.Action(
                    name="stop_steps",
                    tooltip="stop",
                    icon="octagon-x",
                    payload={"msg_id": msg.id}
                ),
                cl.Action(
                    name="execute_steps",
                    tooltip="Next step",
                    icon="fast-forward",
                    payload={"msg_id": msg.id}
                )
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
    port=AGENT_TIDE_PORT,
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
    parser.add_argument("--port", type=int, default=AGENT_TIDE_PORT, help="Port to bind to")
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
    os.environ["AGENT_TIDE_CONFIG_PATH"] = DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
    asyncio.run(init_db(f"{os.environ['CHAINLIT_APP_ROOT']}/database.db"))
    serve()
    # TODO fix the no time being inserted to msg bug in data-persistance
    # TODO there's a bug that changes are not being persistied in untracked files that are deleted so will need to update codetide to track that
    # TODO add chainlit commands for writing tests, updating readme, writing commit message and planning
    # TODO pre release, create hf orchestrator that launches temp dir, clones repo there and stores api config there
    # TODO or just deactivate pre data persistance for hf release
    # TODO need to test project path is working as expected...
