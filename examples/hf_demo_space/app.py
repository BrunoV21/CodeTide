### chainlit app without data persistance enabled
# ruff: noqa: E402
from pathlib import Path
import os

os.environ.setdefault("CHAINLIT_APP_ROOT", str(Path(os.path.abspath(__file__)).parent))

from codetide.agents.tide.ui.defaults import AICORE_CONFIG_EXAMPLE, EXCEPTION_MESSAGE, MISSING_CONFIG_MESSAGE, STARTERS
from codetide.agents.tide.ui.stream_processor import StreamProcessor, MarkerConfig
from codetide.agents.tide.ui.utils import run_concurrent_tasks
from codetide.agents.tide.ui.agent_tide_ui import AgentTideUi
from codetide.core.defaults import DEFAULT_ENCODING
from codetide.core.logs import logger
from codetide.agents.tide.models import Step

from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN
from aicore.models import AuthenticationError, ModelError
from aicore.config import Config
from aicore.llm import Llm

from git_utils import commit_and_push_changes, validate_git_url
from chainlit.cli import run_chainlit
from typing import Optional
from pathlib import Path
from ulid import ulid
import chainlit as cl
import subprocess
import asyncio
import shutil
import json
import stat
import yaml
import os

DEFAULT_SESSIONS_WORKSPACE = Path(os.getcwd()) / "sessions"

async def validate_llm_config_hf(agent_tide_ui: AgentTideUi):
    exception = True
    session_id = cl.user_session.get("session_id")
    while exception:
        try:
            agent_tide_ui.agent_tide.llm.provider.validate_config(force_check_against_provider=True)
            exception = None

        except (AuthenticationError, ModelError) as e:
            exception = e
            await cl.Message(
                content=MISSING_CONFIG_MESSAGE.format(
                    agent_tide_config_path="because-we-dont-actually-store-it-it-only-exists-while-this-session-is-alive",
                    config_file="config-file-in-yaml",
                    example_config=AICORE_CONFIG_EXAMPLE
                ),
                elements=[
                    cl.File(
                        name="config.yml",
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

                    session_dir_path = DEFAULT_SESSIONS_WORKSPACE / session_id
                    if not os.path.exists(session_dir_path):
                        os.makedirs(session_dir_path, exist_ok=True)

                except Exception as e:
                    exception = e

async def loadAgentTideUi()->AgentTideUi:
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    session_id = cl.user_session.get("session_id")
    if agent_tide_ui is None:
        await clone_repo(session_id)

        try:
            agent_tide_ui = AgentTideUi(
                DEFAULT_SESSIONS_WORKSPACE / session_id,
                history=cl.user_session.get("chat_history"),
                llm_config=cl.user_session.get("settings"),
                session_id=session_id
            )
            await agent_tide_ui.load()

        except FileNotFoundError:
            ...

        await validate_llm_config_hf(agent_tide_ui)

        cl.user_session.set("AgentTideUi", agent_tide_ui)

    return agent_tide_ui

async def clone_repo(session_id):
    # TODO ask user actions to get PAT and attempt to clone git repo contents
    exception = True
    
    while exception:
        try:
            user_message = await cl.AskUserMessage(
                content="Provide a valid github url to give AgentTide some context!"
            ).send()
            url = user_message.get("output")
            await validate_git_url(url)
            exception = None
        except Exception as e:
            await cl.Message(f"Invalid url found, please provide only the url, if it is a private repo you can inlucde a PAT in the url: {e}").send()
            exception = e

    logger.info(f"executing cmd git clone --no-checkout {url} {DEFAULT_SESSIONS_WORKSPACE / session_id}")

    process = await asyncio.create_subprocess_exec(
        "git", "clone", url, str(DEFAULT_SESSIONS_WORKSPACE / session_id),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise
    
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, ["git", "clone", url], stdout, stderr)
    
    logger.info(f"finished cloning to {DEFAULT_SESSIONS_WORKSPACE / session_id}")


@cl.on_chat_start
async def start_chatr():
    ### create new dir to clone repo
    ### and yeah force agentTide llm_config to be zreo
    cl.user_session.set("session_id", ulid())
    await cl.context.emitter.set_commands(AgentTideUi.commands)
    cl.user_session.set("chat_history", [])

@cl.set_starters
async def set_starters():
    return [cl.Starter(**kwargs) for kwargs in STARTERS]

@cl.on_chat_end
async def empty_current_session():
    session_id = cl.user_session.get("session_id")
    session_path = DEFAULT_SESSIONS_WORKSPACE / session_id
    if os.path.exists(session_path):
        shutil.rmtree(session_path)

def remove_readonly(func, path, _):
    """Clear the readonly bit and reattempt the removal"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

@cl.on_app_shutdown
async def empty_all_sessions():
    if os.path.exists(DEFAULT_SESSIONS_WORKSPACE):
        shutil.rmtree(DEFAULT_SESSIONS_WORKSPACE, onexc=remove_readonly)

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

@cl.action_callback("checkout_commit_push")
async def on_checkout_commit_push(action :cl.Action):
    session_id = cl.user_session.get("session_id")
    await commit_and_push_changes(DEFAULT_SESSIONS_WORKSPACE / session_id)

@cl.action_callback("inspect_code_context")
async def on_inspect_context(action :cl.Action):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")

    inspect_msg = cl.Message(
        content="",
        author="Agent Tide",
        elements= [
            cl.Text(
                name="CodeTIde Retrieved Identifiers",
                content=f"""```json{json.dumps(list(agent_tide_ui.agent_tide._last_code_identifers), indent=4)}\n```"""
            )
        ]
    )    
    agent_tide_ui.agent_tide._last_code_identifers = None

    if agent_tide_ui.agent_tide._last_code_context:
        inspect_msg.elements.append(
            cl.File(
                name=f"codetide_context_{ulid()}.txt",
                content=agent_tide_ui.agent_tide._last_code_context
            )
        )
        agent_tide_ui.agent_tide._last_code_context = None

    await inspect_msg.send()

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
                    begin_marker="*** Begin Commit",
                    end_marker="*** End Commit",
                    start_wrapper="\n```shell\n",
                    end_wrapper="\n```\n",
                    target_step=msg
                ),
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

        if agent_tide_ui.agent_tide._last_code_identifers:
            msg.actions.append(
                cl.Action(
                    name="inspect_code_context",
                    tooltip="Inspect CodeContext",
                    icon= "telescope",
                    payload={"msg_id": msg.id}
                )
            )

        msg.actions.append(
            cl.Action(
                    name="checkout_commit_push",
                    tooltip="A new branch will be created and the changes made so far will be commited and pushed to the upstream repository",
                    icon="circle-fading-arrow-up",
                    payload={"msg_id": msg.id}
                )
        )
        # # Send the final message
        await msg.send()

        chat_history.append({"role": "assistant", "content": msg.content})
        await agent_tide_ui.add_to_history(msg.content)

if __name__ == "__main__":
    
    # TODO add button button to ckeckout and push
    run_chainlit(os.path.abspath(__file__))