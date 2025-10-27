# ruff: noqa: E402
from pathlib import Path
import os

os.environ.setdefault("CHAINLIT_APP_ROOT", str(Path(os.path.abspath(__file__)).parent))
os.environ.setdefault("CHAINLIT_AUTH_SECRET","@6c1HFdtsjiYKe,-t?dZXnq%4xrgS/YaHte/:Dr6uYq0su/:fGX~M2uy0.ACehaK")

try:
    from aicore.config import Config
    from aicore.llm import Llm, LlmConfig
    from aicore.models import AuthenticationError, ModelError
    from aicore.const import SPECIAL_TOKENS # STREAM_END_TOKEN, STREAM_START_TOKEN#, REASONING_START_TOKEN, REASONING_STOP_TOKEN
    from codetide.agents.tide.ui.utils import process_thread, send_reasoning_msg
    from codetide.agents.tide.ui.persistance import check_docker, launch_postgres
    from codetide.agents.tide.ui.stream_processor import StreamProcessor, MarkerConfig
    from codetide.agents.tide.ui.defaults import AGENT_TIDE_PORT, STARTERS
    from codetide.agents.tide.ui.agent_tide_ui import AgentTideUi
    from codetide.agents.tide.streaming.service import run_concurrent_tasks, cancel_gen
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

from codetide.agents.tide.agent import REASONING_FINISHED, REASONING_STARTED, ROUND_FINISHED
from codetide.agents.tide.ui.stream_processor import CustomElementStep, FieldExtractor
from codetide.agents.tide.ui.defaults import AICORE_CONFIG_EXAMPLE, EXCEPTION_MESSAGE, MISSING_CONFIG_MESSAGE
from codetide.agents.tide.defaults import DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
from codetide.core.defaults import DEFAULT_ENCODING
from dotenv import get_key, load_dotenv, set_key
from codetide.agents.data_layer import init_db
from ulid import ulid
import argparse
import getpass
import asyncio
import secrets
import string
import json
import yaml
import time

if check_docker and os.getenv("AGENTTIDE_PG_CONN_STR") is not None:
    @cl.password_auth_callback
    def auth():
        username = getpass.getuser()
        return cl.User(identifier=username, display_name=username)

    @cl.data_layer
    def get_data_layer():
        return SQLAlchemyDataLayer(conninfo=os.getenv("AGENTTIDE_PG_CONN_STR"))

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
            if hasattr(agent_tide_ui.agent_tide.llm.provider.config, "access_token"):
                exception = None
            else:
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

# Example 1: Partial data with reasoning steps, context and modify identifiers, not finished
example1 = {
    "reasoning_steps": [
        {
            "header": "Initial Analysis",
            "content": "I'm examining the problem statement to understand the requirements and constraints.",
            "candidate_identifiers": ["problem_id", "requirements", "constraints"]
        },
        {
            "header": "Solution Approach",
            "content": "Based on the analysis, I'll implement a solution using a divide-and-conquer strategy.",
            "candidate_identifiers": ["algorithm", "divide_conquer", "implementation"]
        }
    ],
    "context_identifiers": ["user_context", "system_requirements", "api_documentation"],
    "modify_identifiers": ["configuration_settings", "user_preferences"],
    "summary": "",
    "finished": False
}

"""
*** Begin Reasoning
**first task header**
**content**: brief summary of the logic behind this task and the files to look into and why
**candidate_identifiers**:
  - fully qualified code identifiers or file paths (as taken from the repo_tree) that this step might need to use as context
*** End Reasoning
*** Begin Reasoning
**first task header**
**content**: brief summary of the logic behind this task and the files to look into and why
**candidate_identifiers**:
   - fully qualified code identifiers or file paths (as taken from the repo_tree) that this step might need to modify or update
*** End Reasoning
"""
### use current expansion logic here then move to the next one once all possible candidate_identifiers have been found
### decide here together with expand_paths if we need to expand history i.e load older messages

"""
*** Begin Summary
summary of the reasoning steps so far
*** End Summary

*** Begin Context Identifiers
<identifiers - one per line, or empty>
*** End Context Identifiers

*** Begin Modify Identifiers  
<identifiers - one per line, or empty>
*** End Modify Identifiers

"""

# Example 2: Complete data with all fields populated and finished as true
example2 = {
    "reasoning_steps": [
        {
            "header": "Problem Identification",
            "content": "The issue appears to be related to memory management in the application.",
            "candidate_identifiers": ["memory_leak", "heap_overflow", "garbage_collection"]
        },
        {
            "header": "Root Cause Analysis",
            "content": "After thorough investigation, I've identified that objects are not being properly deallocated.",
            "candidate_identifiers": ["object_lifecycle", "destructor", "reference_counting"]
        },
        {
            "header": "Solution Implementation",
            "content": "I'll implement a custom memory pool to better manage object allocation and deallocation.",
            "candidate_identifiers": ["memory_pool", "allocation_strategy", "deallocation"]
        }
    ],
    "context_identifiers": ["application_logs", "performance_metrics", "system_architecture"],
    "modify_identifiers": ["memory_management_module", "allocation_policies"],
    "summary": "This is the final reasoning summary",
    "finished": True
}

# Example 3: Only reasoning steps with no other data
example3 = {
    "reasoning_steps": [
        {
            "header": "Data Collection",
            "content": "Gathering relevant data from various sources to build our dataset.",
            "candidate_identifiers": ["data_sources", "extraction_methods", "validation"]
        },
        {
            "header": "Data Processing",
            "content": "Cleaning and transforming the raw data to make it suitable for analysis.",
            "candidate_identifiers": ["data_cleaning", "transformation", "normalization"]
        },
        {
            "header": "Model Training",
            "content": "Training the machine learning model using the processed dataset.",
            "candidate_identifiers": ["ml_algorithm", "hyperparameters", "training_split"]
        },
        {
            "header": "Model Evaluation",
            "content": "Evaluating the model's performance using various metrics.",
            "candidate_identifiers": ["accuracy", "precision", "recall", "f1_score"]
        }
    ],
    "context_identifiers": [],
    "modify_identifiers": [],
    "finished": False
}

async def get_ticket():
    """Pretending to fetch data from linear"""
    return {
        "title": "Fix Authentication Bug",
        "status": "in-progress",
        "assignee": "Sarah Chen",
        "deadline": "2025-01-15",
        "tags": ["security", "high-priority", "backend"]
    }

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

    # props = await get_ticket()
    
    # ticket_element = cl.CustomElement(name="LinearTicket", props=props)
    # # Store the element if we want to update it server side at a later stage.
    # cl.user_session.set("ticket_el", ticket_element)
    
    # await cl.Message(content="Here is the ticket information!", elements=[ticket_element]).send()

    # await asyncio.sleep(2)
    # ticket_element.props["title"] = "Could not Fix Authentication Bug"
    # await ticket_element.update()

    card_element = cl.CustomElement(name="ReasoningExplorer", props=example1)
    await cl.Message(content="", elements=[card_element]).send()

    # await asyncio.sleep(2)
    # card_element.props.update(example2)
    # await card_element.update()

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
    if agent_tide_ui is None:
        try:
            agent_tide_ui = AgentTideUi(
                os.getenv("AGENT_TIDE_PROJECT_PATH", "./"),
                history=cl.user_session.get("chat_history"),
                llm_config=cl.user_session.get("settings") or None
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
    
        # await cl.send_window_message("Current Steps have beed discarded")

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

@cl.action_callback("approve_patch")
async def on_approve_patch(action :cl.Action):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")

    await action.remove()
    latest_action_message :cl.Message = cl.user_session.get("latest_patch_msg")
    if latest_action_message.id == action.payload.get("action_id"):
        latest_action_message.actions = []

    if action.payload.get("lgtm"):
        agent_tide_ui.agent_tide.approve()

@cl.action_callback("reject_patch")
async def on_reject_patch(action :cl.Action):
    agent_tide_ui: AgentTideUi = cl.user_session.get("AgentTideUi")
    chat_history = cl.user_session.get("chat_history")

    await action.remove()
    latest_action_message :cl.Message = cl.user_session.get("latest_patch_msg")
    if latest_action_message.id == action.payload.get("action_id"):
        latest_action_message.actions = []

    response = await cl.AskUserMessage(
        content="""Please provide specific feedback explaining why the patch was rejected. Include what's wrong, which parts are problematic, and what needs to change. Avoid vague responses like "doesn't work" - instead be specific like "missing error handling for FileNotFoundError" or "function should return boolean, not None." Your detailed feedback helps generate a better solution.""",
        timeout=3600
    ).send()

    feedback = response.get("output")
    agent_tide_ui.agent_tide.reject(feedback)
    chat_history.append({"role": "user", "content": feedback})
    await agent_loop(agent_tide_ui=agent_tide_ui)

@cl.on_message
async def agent_loop(message: Optional[cl.Message]=None, codeIdentifiers: Optional[list] = None, agent_tide_ui :Optional[AgentTideUi]=None):

    # loading_msg = await cl.Message(
    #     content="",
    #     elements=[
    #         cl.CustomElement(
    #             name="LoadingMessage",
    #             props={
    #                 "messages": ["Working", "Syncing CodeTide", "Thinking", "Looking for context"],
    #                 "interval": 1500,  # 1.5 seconds between messages
    #                 "showIcon": True
    #             }
    #         )
    #     ]
    # ).send()

    if agent_tide_ui is None:
        agent_tide_ui = await loadAgentTideUi()

    chat_history = cl.user_session.get("chat_history")
    
    if message is not None:
        if message.command:
            command_prompt = await agent_tide_ui.get_command_prompt(message.command)
            if command_prompt:
                message.content = "\n\n---\n\n".join([command_prompt, message.content])

        chat_history.append({"role": "user", "content": message.content})
        await agent_tide_ui.add_to_history(message.content, is_input=True)

    reasoning_element = cl.CustomElement(name="ReasoningExplorer", props={
        "reasoning_steps": [],
        "summary": "",
        "context_identifiers": [], # amrker
        "modify_identifiers": [],
        "finished": False,
        "thinkingTime": 0
    })

    if not agent_tide_ui.agent_tide._skip_context_retrieval:
        reasoning_mg = cl.Message(content="", author="AgentTide", elements=[reasoning_element])
        _ = await reasoning_mg.send()
    ### TODO this needs to receive the message as well to call update
    reasoning_step = CustomElementStep(
        element=reasoning_element,
        props_schema = {
            "reasoning_steps": list,  # Will accumulate reasoning blocks as list
            "summary": str,
            "context_identifiers": list,
            "modify_identifiers": list
        }
    )


    msg = cl.Message(content="", author="Agent Tide")

    # ReasoningCustomElementStep = CustomElementStep()

    async with cl.Step("ApplyPatch", type="tool") as diff_step:
        await diff_step.remove()

        # Initialize the stream processor
        stream_processor = StreamProcessor(
            marker_configs=[
                MarkerConfig(
                    begin_marker="*** Begin Patch",
                    end_marker="*** End Patch",
                    start_wrapper="\n```diff\n",
                    end_wrapper="\n```\n",
                    target_step=diff_step
                ),
                MarkerConfig(
                    begin_marker="*** Begin Steps",
                    end_marker="*** End Steps",
                    start_wrapper="\n```shell\n",
                    end_wrapper="\n```\n",
                    target_step=msg
                ),
                MarkerConfig(
                    begin_marker="*** Begin Commit",
                    end_marker="*** End Commit",
                    start_wrapper="\n```shell\n",
                    end_wrapper="\n```\n",
                    target_step=msg
                ), 
                MarkerConfig(
                    marker_id="reasoning_steps",
                    begin_marker="*** Begin Reasoning",
                    end_marker="*** End Reasoning",
                    target_step=reasoning_step,
                    stream_mode="full",
                    field_extractor=FieldExtractor({
                        "header": r"\*{0,2}Task\*{0,2}:\s*(.+?)(?=\n\s*\*{0,2}Rationale\*{0,2})",
                        "content": r"\*{0,2}Rationale\*{0,2}:\s*(.+?)(?=\s*\*{0,2}Candidate Identifiers\*{0,2}|$)",
                        "candidate_identifiers": {"pattern": r"^\s*-\s*(.+?)$", "schema": list}
                    })
                ),
                MarkerConfig(
                    marker_id="summary",
                    begin_marker="*** Begin Summary",
                    end_marker="*** End Summary",
                    target_step=reasoning_step,
                    stream_mode="full"
                    ### TODO update marker_config so that default field_extractor returns marker_id: contents as string
                    ### or list or whatever is specified
                    ### format should be {markerd_id, no_regex + type if None set to str}
                ),
                MarkerConfig(
                    marker_id="context_identifiers",
                    begin_marker="*** Begin Context Identifiers",
                    end_marker="*** End Context Identifiers",
                    target_step=reasoning_step,
                    stream_mode="full"
                ),
                MarkerConfig(
                    marker_id="modify_identifiers",
                    begin_marker="*** Begin Modify Identifiers",
                    end_marker="*** End Modify Identifiers",
                    target_step=reasoning_step,
                    stream_mode="full"
                )
            ],
            global_fallback_msg=msg
        )

        reasoning_start_time = time.time()
        loop = run_concurrent_tasks(agent_tide_ui, codeIdentifiers)
        async for chunk in loop:
            ### TODO update this to check FROM AGENT TIDE if reasoning is being ran and if so we need
            ### to send is finished true to custom element when the next STREAM_START_TOKEN_arrives

            if chunk in SPECIAL_TOKENS:
                continue
            #     is_reasonig_sent = await send_reasoning_msg(loading_msg, context_msg, agent_tide_ui, st)
            #     continue

            # elif not is_reasonig_sent:
            #     is_reasonig_sent = await send_reasoning_msg(loading_msg, context_msg, agent_tide_ui, st)
            elif chunk == REASONING_STARTED:
                stream_processor.global_fallback_msg = None
                stream_processor.buffer = ""
                stream_processor.accumulated_content = ""
                continue
            elif chunk == REASONING_FINISHED:
                reasoning_end_time = time.time()
                thinking_time = int(reasoning_end_time - reasoning_start_time)
                stream_processor.global_fallback_msg = msg
                stream_processor.buffer = ""
                stream_processor.accumulated_content = ""
                reasoning_element.props["finished"] = True
                reasoning_element.props["thinkingTime"] = thinking_time
                await reasoning_element.update()
                continue
                
            elif chunk == ROUND_FINISHED:
                #  Handle any remaining content
                await stream_processor.finalize()
                await asyncio.sleep(0.5)
                await cancel_gen(loop)

            await stream_processor.process_chunk(chunk)
        
        await asyncio.sleep(0.5)
        if agent_tide_ui.agent_tide.steps:
            cl.user_session.set("latest_step_message", msg)
            msg.actions = [
                cl.Action(
                    name="stop_steps",
                    tooltip="Stop",
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

    # Send the final message
    await msg.send()

    chat_history.append({"role": "assistant", "content": msg.content})
    await agent_tide_ui.add_to_history(msg.content)

    if agent_tide_ui.agent_tide._has_patch:
        action_msg = cl.AskActionMessage(
            content="AgentTide is asking you to review the Patch before applying it.",
            actions=[],
            timeout=3600
        )
        action_msg.actions = [
            cl.Action(name="approve_patch", payload={"lgtm": True, "msg_id": action_msg.id}, label="✔️ Approve"),
            cl.Action(name="reject_patch", payload={"lgtm": False, "msg_id": action_msg.id}, label="❌ Reject")
        ]
        cl.user_session.set("latest_patch_msg", action_msg)
        choice = await action_msg.send()

        if choice:
            lgtm = choice.get("payload", []).get("lgtm")
            if lgtm:
                action_msg.actions = []
                agent_tide_ui.agent_tide.approve()
            else:
                action_msg.actions = []
                response = await cl.AskUserMessage(
                    content="""Please provide specific feedback explaining why the patch was rejected. Include what's wrong, which parts are problematic, and what needs to change. Avoid vague responses like "doesn't work" - instead be specific like "missing error handling for FileNotFoundError" or "function should return boolean, not None." Your detailed feedback helps generate a better solution.""",
                    timeout=3600
                ).send()

                feedback = response.get("output")
                agent_tide_ui.agent_tide.reject(feedback)
                chat_history.append({"role": "user", "content": feedback})
                await agent_loop(agent_tide_ui=agent_tide_ui)

def generate_password(length: int = 16) -> str:
    """
    Generate a secure random password.
    Works on Linux, macOS, and Windows.
    """
    if password  := get_key(Path(os.environ['CHAINLIT_APP_ROOT']) / ".env", "AGENTTDE_PG_PASSWORD"):
        return password
    
    safe_chars = string.ascii_letters + string.digits + '-_@#$%^&*+=[]{}|:;<>?'
    password = ''.join(secrets.choice(safe_chars) for _ in range(length))
    set_key(Path(os.environ['CHAINLIT_APP_ROOT']) / ".env","AGENTTDE_PG_PASSWORD", password)
    return password

def serve(
    host=None,
    port=AGENT_TIDE_PORT,
    root_path=None,
    ssl_certfile=None,
    ssl_keyfile=None,
    ws_per_message_deflate="true",
    ws_protocol="auto"
):
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
    parser = argparse.ArgumentParser(
        description="Launch the Tide UI server.",
        epilog=(
            "\nAvailable commands and what they do:\n"
            "  --host                Host to bind to (default: None)\n"
            "  --port                Port to bind to (default: 9753)\n"
            "  --root-path           Root path for the app (default: None)\n"
            "  --ssl-certfile        Path to SSL certificate file (default: None)\n"
            "  --ssl-keyfile         Path to SSL key file (default: None)\n"
            "  --ws-per-message-deflate  WebSocket per-message deflate (true/false, default: true)\n"
            "  --ws-protocol         WebSocket protocol (default: auto)\n"
            "  --project-path        Path to the project directory (default: ./)\n"
            "  --config-path         Path to the config file (default: .agent_tide_config.yml)\n"
            "  -h, --help            Show this help message and exit\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
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

    load_dotenv()
    os.environ["AGENT_TIDE_PROJECT_PATH"] = str(Path(args.project_path))
    os.environ["AGENT_TIDE_CONFIG_PATH"] = str(Path(args.project_path) / args.config_path)
    
    load_dotenv()
    username = getpass.getuser()
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"

    print(f"\n{GREEN}Your chainlit username is `{username}`{RESET}\n")

    if check_docker():
        password = generate_password()
        launch_postgres(username, password, f"{os.environ['CHAINLIT_APP_ROOT']}/pgdata")
    
        conn_string = f"postgresql+asyncpg://{username}:{password}@localhost:{os.getenv('AGENTTIDE_PG_PORT', 5437)}/agenttidedb"
        os.environ["AGENTTIDE_PG_CONN_STR"] = conn_string
        asyncio.run(init_db(os.environ["AGENTTIDE_PG_CONN_STR"]))

        print(f"{GREEN} PostgreSQL launched on port {os.getenv('AGENTTIDE_PG_PORT', 5437)}{RESET}")
        print(f"{GREEN} Connection string stored in env var: AGENTTIDE_PG_CONN_STR{RESET}\n")
    else:
        print(f"{RED} Could not find Docker on this system.{RESET}")
        print("   PostgreSQL could not be launched for persistent data storage.")
        print("   You won't have access to multiple conversations or history beyond each session.")
        print("   Consider installing Docker and ensuring it is running.\n")

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
    main()

# if __name__ == "__main__":
#     import asyncio
#     os.environ["AGENT_TIDE_CONFIG_PATH"] = DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
#     asyncio.run(init_db(f"{os.environ['CHAINLIT_APP_ROOT']}/database.db"))
#     serve()
    # TODO fix the no time being inserted to msg bug in data-persistance
    # TODO there's a bug that changes are not being persistied in untracked files that are deleted so will need to update codetide to track that
    # TODO add chainlit commands for writing tests, updating readme, writing commit message and planning
    # TODO pre release, create hf orchestrator that launches temp dir, clones repo there and stores api config there
    # TODO or just deactivate pre data persistance for hf release
    # TODO need to test project path is working as expected...

    # TODO need to revisit logic
    # TODO there's a bug that is leaving step messages holding for some reason
    # TODO check initialzie codetide logic, seems to be deserialzied a bit too often
    # TODO review codetide check for updat4es - continously readding untracked files

    # TODO check why HF-DEMO-SPACE Auth is being triggereds
