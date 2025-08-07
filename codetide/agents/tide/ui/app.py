# ruff: noqa: E402
from pathlib import Path
import os

os.environ.setdefault("CHAINLIT_APP_ROOT", str(Path(os.path.abspath(__file__)).parent))
os.environ.setdefault("CHAINLIT_AUTH_SECRET","@6c1HFdtsjiYKe,-t?dZXnq%4xrgS/YaHte/:Dr6uYq0su/:fGX~M2uy0.ACehaK")

try:
    from aicore.llm import Llm, LlmConfig
    from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN#, REASONING_START_TOKEN, REASONING_STOP_TOKEN
    from codetide.agents.tide.ui.stream_processor import StreamProcessor, MarkerConfig
    from codetide.agents.tide.ui.utils import process_thread, run_concurrent_tasks
    from codetide.agents.tide.ui.agent_tide_ui import AgentTideUi
    from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
    from chainlit.types import ThreadDict
    from chainlit.cli import run_chainlit
    import chainlit as cl
      
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' and 'chainlit' packages. "
        "Install it with: pip install codetide[agents-ui]"
    ) from e

from codetide.agents.tide.defaults import DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
from codetide.agents.data_layer import init_db
import argparse
import getpass
import asyncio

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

@cl.action_callback("execute_steps")
async def on_action(action):    
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")


    # await cl.Message(content=f"Executed {action.name}").send()
    

    if agent_tide_ui.current_step is None:
        task_list = cl.TaskList("Steps")
        task_list.status = "Executing step 0"
        for step in agent_tide_ui.agent_tide.steps.root:
            # message = await cl.Message(
            #     content=f"Step {step.step}.\n\n**Instructions**:\n{step.instructions}",
            #     metadata={"context_identifiers": step.context_identifiers}
            # ).send()
            task = cl.Task(title=step.description)#, forId=message.id)
            await task_list.add_task(task)

        # Update the task list in the interface
        await task_list.send()
    
    is_last = agent_tide_ui.increment_step()
    # Optionally remove the action button from the chatbot user interface

    if is_last:
        await action.remove()        
        await task_list.remove()

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
            if agent_tide_ui.current_step is None:
                label="Run Steps One by One"
            elif agent_tide_ui.current_step == len(agent_tide_ui.agent_tide.steps.root) -1:
                label = "Close Steps List"
            else:
                label = f"Proceed to step {agent_tide_ui.current_step+1}"
 
            msg.actions = [
                cl.Action(
                    name="execute_steps", 
                    payload={"step": "example_value"},
                    label=label
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