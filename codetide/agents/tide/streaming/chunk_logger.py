from ....core.defaults import DEFAULT_ENCODING
from aicore.logger import SPECIAL_TOKENS

from typing import List, Dict, AsyncGenerator
from collections import defaultdict, deque
from pathlib import Path
import portalocker
import asyncio
import time

class ChunkLogger:
    def __init__(self, buffer_size: int = 1024, flush_interval: float = 0.1):
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self._session_buffers: Dict[str, deque] = defaultdict(deque)
        self._session_subscribers: Dict[str, List] = defaultdict(list)
        self._file_buffers: Dict[str, List[str]] = defaultdict(list)
        self._last_flush_time: Dict[str, float] = defaultdict(float)
        self._background_tasks: set = set()
        self._shutdown = False
        
    async def log_chunk(self, message: str, session_id: str, filepath: str):
        """Optimized chunk logging with batched file writes and direct streaming"""
        if message not in SPECIAL_TOKENS:
            # Add to file buffer for batched writing
            self._file_buffers[filepath].append(message)
            current_time = time.time()
            
            # Check if we should flush based on buffer size or time
            should_flush = (
                len(self._file_buffers[filepath]) >= self.buffer_size or
                current_time - self._last_flush_time[filepath] >= self.flush_interval
            )
            
            if should_flush:
                await self._flush_file_buffer(filepath)
                self._last_flush_time[filepath] = current_time
        
        # Directly notify subscribers without queue overhead
        await self._notify_subscribers(session_id, message)
    
    async def _flush_file_buffer(self, filepath: str):
        """Flush buffer to file with file locking"""
        if not self._file_buffers[filepath]:
            return
            
        messages_to_write = self._file_buffers[filepath].copy()
        self._file_buffers[filepath].clear()
        
        # Create directory if it doesn't exist
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Use portalocker for safe concurrent file access
            with open(filepath, 'a', encoding=DEFAULT_ENCODING) as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                try:
                    f.writelines(messages_to_write)
                    f.flush()  # Ensure data is written to disk
                finally:
                    portalocker.unlock(f)
        except Exception as e:
            # Re-add messages to buffer if write failed
            self._file_buffers[filepath].extendleft(reversed(messages_to_write))
            raise e
    
    async def _notify_subscribers(self, session_id: str, message: str):
        """Directly notify subscribers without queue overhead"""
        if session_id in self._session_subscribers:
            # Use a list copy to avoid modification during iteration
            subscribers = list(self._session_subscribers[session_id])
            for queue in subscribers:
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    # Remove full queues (slow consumers)
                    self._session_subscribers[session_id].remove(queue)
                except Exception:
                    # Remove invalid queues
                    if queue in self._session_subscribers[session_id]:
                        self._session_subscribers[session_id].remove(queue)
    
    async def get_session_logs(self, session_id: str) -> AsyncGenerator[str, None]:
        """Get streaming logs for a session without separate distributor task"""
        # Create a queue for this subscriber
        queue = asyncio.Queue(maxsize=1000)  # Prevent memory issues
        
        # Add to subscribers
        self._session_subscribers[session_id].append(queue)
        
        try:
            while not self._shutdown:
                try:
                    # Use a timeout to allow for cleanup checks
                    chunk = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield chunk
                except asyncio.TimeoutError:
                    # Check if we should continue or if there are no more publishers
                    continue
                except asyncio.CancelledError:
                    break
        finally:
            # Cleanup subscriber
            if queue in self._session_subscribers[session_id]:
                self._session_subscribers[session_id].remove(queue)
            
            # Clean up empty session entries
            if not self._session_subscribers[session_id]:
                del self._session_subscribers[session_id]
    
    async def ensure_all_flushed(self):
        """Ensure all buffers are flushed - call before shutdown"""
        flush_tasks = []
        for filepath in list(self._file_buffers.keys()):
            if self._file_buffers[filepath]:
                flush_tasks.append(self._flush_file_buffer(filepath))
        
        if flush_tasks:
            await asyncio.gather(*flush_tasks, return_exceptions=True)
    
    async def shutdown(self):
        """Graceful shutdown"""
        self._shutdown = True
        await self.ensure_all_flushed()
        
        # Cancel any background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
