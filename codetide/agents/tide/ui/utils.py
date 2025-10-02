from codetide.agents.tide.ui.agent_tide_ui import AgentTideUi

from typing import List, Optional, Tuple
from chainlit.types import ThreadDict
from aicore.logger import _logger
from aicore.llm import LlmConfig
import chainlit as cl
import asyncio
import orjson
import time

def process_thread(thread :ThreadDict)->Tuple[List[dict], Optional[LlmConfig], str]:
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
        session_id = metadata.get("session_id")
    else:
        history = []
        settings = None
        session_id = None

    return history, settings, session_id

async def run_concurrent_tasks(agent_tide_ui: AgentTideUi, codeIdentifiers :Optional[List[str]]=None):
    asyncio.create_task(agent_tide_ui.agent_tide.agent_loop(codeIdentifiers))
    asyncio.create_task(_logger.distribute())
    while True:
        async for chunk in _logger.get_session_logs(agent_tide_ui.agent_tide.llm.session_id):
            yield chunk

async def send_reasoning_msg(loading_msg :cl.message, context_msg :cl.Message, agent_tide_ui :AgentTideUi, st :float)->bool:
    await loading_msg.remove()

    context_data = {
        key: value for key in ["contextIdentifiers", "modifyIdentifiers"]
        if (value := getattr(agent_tide_ui.agent_tide, key, None))
    }
    context_msg.elements.append(
        cl.CustomElement(
            name="ReasoningMessage",
            props={
                "reasoning": agent_tide_ui.agent_tide.reasoning,
                "data": context_data,
                "title": f"Thought for {time.time()-st:.2f} seconds",
                "defaultExpanded": False,
                "showControls": False
            }
        )
    )
    await context_msg.send()
    return True


### Wrap thus send_reasoning_msg into a custom object which receives a loading_msg a context_msg and a st
### should also receive a dict with arguments (props) to be used internaly when calling stream_token (which will always receive a string)
### include stream_token method 
### do not remove laoding message for now
### start with expanded template with wave animation and placeholder
### custom obj should preserve props and update them with new args, markerconfig should be update to include args per
### config as well as possibility to dump only once filled and convert to type i.e json loads to list / dict by is_obj prooperty)
### dumping only when buffer is complete should be handled at streamprocessor level
