from .chunk_logger import ChunkLogger
from typing import Optional
import asyncio

class BackgroundFlusher:
    """
    # For very high throughput, you can use the background flusher:
    background_flusher = BackgroundFlusher(_optimized_logger, flush_interval=0.05)
    await background_flusher.start()

    # ... your application code ...

    # Clean shutdown
    await background_flusher.stop()
    await _optimized_logger.shutdown()
    """
    def __init__(self, logger: ChunkLogger, flush_interval: float = 0.1):
        self.logger = logger
        self.flush_interval = flush_interval
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start background flushing task"""
        if self._task and not self._task.done():
            return
        
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())
        self.logger._background_tasks.add(self._task)
    
    async def stop(self):
        """Stop background flushing"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _flush_loop(self):
        """Background flush loop"""
        try:
            while self._running:
                await asyncio.sleep(self.flush_interval)
                if not self._running:
                    break
                
                # Flush all file buffers
                flush_tasks = []
                for filepath in list(self.logger._file_buffers.keys()):
                    if self.logger._file_buffers[filepath]:
                        flush_tasks.append(self.logger._flush_file_buffer(filepath))
                
                if flush_tasks:
                    await asyncio.gather(*flush_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass  # Ignore errors in background task
