from codetide.agents.tide.ui.agent_tide_ui import AgentTideUi

from typing import List, Optional, Tuple
from chainlit.types import ThreadDict
from aicore.logger import _logger
from aicore.llm import LlmConfig
import asyncio
import orjson

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

async def run_concurrent_tasks(agent_tide_ui: AgentTideUi):
    asyncio.create_task(agent_tide_ui.agent_tide.agent_loop_planing())
    asyncio.create_task(_logger.distribute())
    while True:
        async for chunk in _logger.get_session_logs(agent_tide_ui.agent_tide.llm.session_id):
            yield chunk