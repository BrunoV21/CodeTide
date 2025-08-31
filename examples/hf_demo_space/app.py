### chainlit app without data persistance enabled
# ruff: noqa: E402
from pathlib import Path
import os

os.environ.setdefault("CHAINLIT_APP_ROOT", str(Path(os.path.abspath(__file__)).parent))

from codetide.agents.tide.ui.defaults import AICORE_CONFIG_EXAMPLE, EXCEPTION_MESSAGE, MISSING_CONFIG_MESSAGE, STARTERS
from codetide.agents.tide.ui.stream_processor import StreamProcessor, MarkerConfig
from codetide.agents.tide.ui.utils import run_concurrent_tasks
from codetide.agents.tide.ui.agent_tide_ui import AgentTideUi
from codetide.agents.tide.ui.app import send_reasoning_msg
from codetide.core.defaults import DEFAULT_ENCODING
from codetide.core.logs import logger
from codetide.agents.tide.models import Step

from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN
from aicore.models import AuthenticationError, ModelError
from aicore.llm import Llm, LlmConfig
from aicore.config import Config

from git_utils import commit_and_push_changes, validate_git_url, checkout_new_branch
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
import time
import os

DEFAULT_SESSIONS_WORKSPACE = Path(os.getcwd()) / "sessions"

@cl.on_chat_start
async def start_chat():
    session_id = ulid()
    cl.user_session.set("session_id", session_id)
    await cl.context.emitter.set_commands(AgentTideUi.commands)
    cl.user_session.set("chat_history", [])
    
    exception = True
    while exception:
        try:
            user_message = await cl.AskUserMessage(
                content="Provide a valid github url to give AgentTide some context!",
                timeout=3600
            ).send()
            url = user_message.get("output")
            await validate_git_url(url)
            exception = None
        except Exception as e:
            await cl.Message(f"Invalid url found, please provide only the url, if it is a private repo you can inlucde a PAT in the url: {e}").send()
            exception = e

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

    res = await cl.AskActionMessage(
        content="Select the LLM to power Agent Tide! You can use one of the following free options or configure your own via api key! We recommend `gpt-4.1` or `sonnet-4` for ultimate performance (don't worry we are not logging api keys, you can check the code yourself)! Bear in mind that free alternatives can be context and rate limited.",
        actions=[
            cl.Action(name="kimi-k2", payload={"model": "moonshotai/kimi-k2:free"}, label="kimi-k2"),
            cl.Action(name="qwen3-coder", payload={"model": "qwen/qwen3-coder:free"}, label="qwen3-coder"),
            cl.Action(name="gpt-oss-20b", payload={"model": "openai/gpt-oss-20b:free"}, label="gpt-oss-20b"),
            cl.Action(name="custom", payload={"model": "custom"}, label="bring your model")
        ],
        timeout=3600
    ).send()
    

    if res and res.get("payload").get("model") != "custom":
        llm_config = LlmConfig(
            provider="openrouter",
            model=res.get("payload").get("model"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS"))
        )
        agent_tide_ui = AgentTideUi(
            DEFAULT_SESSIONS_WORKSPACE / session_id,
            history=cl.user_session.get("chat_history"),
            llm_config=llm_config,
            session_id=session_id
        )
        await agent_tide_ui.load()

    elif  res.get("payload").get("model") == "custom":
        agent_tide_ui = AgentTideUi(
            DEFAULT_SESSIONS_WORKSPACE / session_id,
            history=cl.user_session.get("chat_history"),
            llm_config=cl.user_session.get("settings") or None,
            session_id=session_id
        )
        await agent_tide_ui.load()

        exception = True
        
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
                        agent_tide_ui.agent_tide.pass_custom_logger_fn()

                        session_dir_path = DEFAULT_SESSIONS_WORKSPACE / session_id
                        if not os.path.exists(session_dir_path):
                            os.makedirs(session_dir_path, exist_ok=True)

                    except Exception as e:
                        exception = e
    
    await cl.Message(
        content="Hi, I'm Tide... Nice to meet you!"
    ).send()

    new_branch_name = f"agent-tide-{ulid()}"
    cl.user_session.set("current_branch_name", new_branch_name)
    checkout_new_branch(agent_tide_ui.agent_tide.tide.repo, new_branch_name=new_branch_name)
    cl.user_session.set("AgentTideUi", agent_tide_ui)

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
        await latest_step_message.send() # close message ?

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

        await agent_loop(step_instructions_msg, codeIdentifiers=step.get_code_identifiers(agent_tide_ui.agent_tide.tide._as_file_paths), agent_tide_ui=agent_tide_ui)
        
        task_list.status = f"Waiting feedback on step {current_task_idx}"
        await task_list.send()
    
@cl.action_callback("stop_steps")
async def on_stop_steps(action :cl.Action):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")

    latest_step_message :cl.Message = cl.user_session.get("latest_step_message")
    if latest_step_message and latest_step_message.id == action.payload.get("msg_id"):
        await latest_step_message.remove_actions()
        await latest_step_message.send() # close message ?
    
    task_list = cl.user_session.get("StepsTaskList")
    if task_list:
        agent_tide_ui.current_step = None 
        await task_list.remove()

@cl.action_callback("checkout_commit_push")
async def on_checkout_commit_push(action :cl.Action):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    # await agent_tide_ui.agent_tide.prepare_commit()
    # agent_tide_ui.agent_tide.commit("AgentTide - add all and push")
    await commit_and_push_changes(agent_tide_ui.agent_tide.tide.rootpath, branch_name=cl.user_session.get("current_branch_name"), commit_message="AgentTide - add all and push", checkout=False)

@cl.action_callback("inspect_code_context")
async def on_inspect_context(action :cl.Action):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")

    await action.remove()

    inspect_msg = cl.Message(
        content="",
        author="Agent Tide",
        elements= [
            cl.Text(
                name="CodeTIde Retrieved Identifiers",
                content=f"""```json\n{json.dumps(list(agent_tide_ui.agent_tide._last_code_identifers), indent=4)}\n```"""
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
async def agent_loop(message: Optional[cl.Message]=None, codeIdentifiers: Optional[list] = None, agent_tide_ui :Optional[AgentTideUi]=None):

    loading_msg = await cl.Message(
        content="",
        elements=[
            cl.CustomElement(
                name="LoadingMessage",
                props={
                    "messages": ["Working", "Syncing CodeTide", "Thinking", "Looking for context"],
                    "interval": 1500,  # 1.5 seconds between messages
                    "showIcon": True
                }
            )
        ]
    ).send()

    if agent_tide_ui is None:
        agent_tide_ui = cl.user_session.get("AgentTideUi")

    chat_history = cl.user_session.get("chat_history")
    
    if message is not None:
        if message.command:
            command_prompt = await agent_tide_ui.get_command_prompt(message.command)
            if command_prompt:
                message.content = "\n\n---\n\n".join([command_prompt, message.content])

        chat_history.append({"role": "user", "content": message.content})
        await agent_tide_ui.add_to_history(message.content)

    context_msg = cl.Message(content="", author="AgentTide")
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

        st = time.time()
        is_reasonig_sent = False
        async for chunk in run_concurrent_tasks(agent_tide_ui, codeIdentifiers):
            if chunk == STREAM_START_TOKEN:
                is_reasonig_sent = await send_reasoning_msg(loading_msg, context_msg, agent_tide_ui, st)
                continue

            elif not is_reasonig_sent:
                is_reasonig_sent = await send_reasoning_msg(loading_msg, context_msg, agent_tide_ui, st)

            elif chunk == STREAM_END_TOKEN:
                #  Handle any remaining content
                await stream_processor.finalize()
                break

            await stream_processor.process_chunk(chunk)

        await asyncio.sleep(0.5)
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

    # Send the final message
    await msg.send()

    chat_history.append({"role": "assistant", "content": msg.content})
    await agent_tide_ui.add_to_history(msg.content)

    if agent_tide_ui.agent_tide._has_patch:
        choice = await cl.AskActionMessage(
            content="AgentTide is asking you to review the Patch before applying it.",
            actions=[
                cl.Action(name="approve_patch", payload={"lgtm": True}, label="✔️ Approve"),
                cl.Action(name="reject_patch", payload={"lgtm": False}, label="❌ Reject"),
            ],
            timeout=3600
        ).send()

        if choice:
            lgtm = choice.get("payload", []).get("lgtm")
            if lgtm:
                agent_tide_ui.agent_tide.approve()
            else:
                response = await cl.AskUserMessage(
                    content="""Please provide specific feedback explaining why the patch was rejected. Include what's wrong, which parts are problematic, and what needs to change. Avoid vague responses like "doesn't work" - instead be specific like "missing error handling for FileNotFoundError" or "function should return boolean, not None." Your detailed feedback helps generate a better solution.""",
                    timeout=3600
                ).send()

                feedback = response.get("output")
                agent_tide_ui.agent_tide.reject(feedback)
                chat_history.append({"role": "user", "content": feedback})
                await agent_loop(agent_tide_ui=agent_tide_ui)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # TODO add button button to ckeckout and push
    run_chainlit(os.path.abspath(__file__))