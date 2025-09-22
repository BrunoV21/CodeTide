from .chunk_logger import ChunkLogger

from aicore.logger import SPECIAL_TOKENS
from typing import List, Optional
from contextlib import suppress
import asyncio

# Global logger instance
_chunk_logger = ChunkLogger(buffer_size=512, flush_interval=0.001)

async def custom_logger_fn(message: str, session_id: str, filepath: str):
    """Optimized logger function - much faster than queue-based approach"""
    if message not in SPECIAL_TOKENS:
        print(message, end="")
    await _chunk_logger.log_chunk(message, session_id, filepath)

async def run_concurrent_tasks(agent_tide_ui, codeIdentifiers: Optional[List[str]] = None):
    """Simplified concurrent task runner - no separate distributor needed"""
    # Start the agent loop
    agent_task = asyncio.create_task(
        agent_tide_ui.agent_tide.agent_loop(codeIdentifiers)
    )
    
    try:
        # Direct streaming without separate distributor task
        async for chunk in _chunk_logger.get_session_logs(
            agent_tide_ui.agent_tide.llm.session_id
        ):
            yield chunk
    finally:
        # Cleanup: cancel agent task if still running
        if not agent_task.done():
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass

async def cancel_gen(agen):
    task = asyncio.create_task(agen.__anext__())
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    await agen.aclose()
