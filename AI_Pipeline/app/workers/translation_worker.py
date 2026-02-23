"""
Translation worker pool for parallel processing.
"""
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from app.config import get_logger, get_settings
from app.pipeline.translate import get_translator
from app.utils.exceptions import WorkerError

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class TranslationTask:
    """Translation task."""
    task_id: str
    text: str
    source_lang: str
    target_lang: str
    user_id: str
    callback: Optional[Any] = None


@dataclass
class TranslationResult:
    """Translation result."""
    task_id: str
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    processing_time_ms: float


class TranslationWorker:
    """Worker for processing translation tasks."""
    
    def __init__(self, worker_id: int):
        """Initialize worker.
        
        Args:
            worker_id: Worker identifier
        """
        self.worker_id = worker_id
        self.translator = get_translator()
        self.is_busy = False
        self.current_task: Optional[TranslationTask] = None
        
        logger.info("translation_worker_initialized", worker_id=worker_id)
    
    async def process_task(self, task: TranslationTask) -> TranslationResult:
        """Process translation task.
        
        Args:
            task: Translation task
            
        Returns:
            Translation result
        """
        import time
        start_time = time.time()
        
        self.is_busy = True
        self.current_task = task
        
        try:
            logger.debug(
                "worker_processing_task",
                worker_id=self.worker_id,
                task_id=task.task_id
            )
            
            # Perform translation
            translated = await self.translator.translate(
                task.text,
                task.source_lang,
                task.target_lang
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            result = TranslationResult(
                task_id=task.task_id,
                original_text=task.text,
                translated_text=translated,
                source_lang=task.source_lang,
                target_lang=task.target_lang,
                processing_time_ms=processing_time
            )
            
            logger.info(
                "worker_task_complete",
                worker_id=self.worker_id,
                task_id=task.task_id,
                processing_time_ms=processing_time
            )
            
            return result
        
        finally:
            self.is_busy = False
            self.current_task = None


class TranslationWorkerPool:
    """Pool of translation workers."""
    
    def __init__(self, num_workers: int = 4):
        """Initialize worker pool.
        
        Args:
            num_workers: Number of workers
        """
        self.num_workers = num_workers
        self.workers = [TranslationWorker(i) for i in range(num_workers)]
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_tasks = []
        
        logger.info("translation_worker_pool_initialized", workers=num_workers)
    
    async def start(self) -> None:
        """Start worker pool."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker tasks
        for worker in self.workers:
            task = asyncio.create_task(self._worker_loop(worker))
            self._worker_tasks.append(task)
        
        logger.info("translation_worker_pool_started")
    
    async def stop(self) -> None:
        """Stop worker pool."""
        self._running = False
        
        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        self._worker_tasks.clear()
        logger.info("translation_worker_pool_stopped")
    
    async def _worker_loop(self, worker: TranslationWorker) -> None:
        """Worker processing loop.
        
        Args:
            worker: Worker instance
        """
        while self._running:
            try:
                # Get task from queue (with timeout)
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                
                # Process task
                result = await worker.process_task(task)
                
                # Execute callback if provided
                if task.callback:
                    await task.callback(result)
                
                # Mark task as done
                self.task_queue.task_done()
            
            except asyncio.TimeoutError:
                continue
            
            except asyncio.CancelledError:
                break
            
            except Exception as e:
                logger.error(
                    "worker_loop_error",
                    worker_id=worker.worker_id,
                    error=str(e),
                    exc_info=True
                )
    
    async def submit_task(self, task: TranslationTask) -> None:
        """Submit task to pool.
        
        Args:
            task: Translation task
        """
        await self.task_queue.put(task)
        
        logger.debug(
            "task_submitted",
            task_id=task.task_id,
            queue_size=self.task_queue.qsize()
        )
    
    def get_queue_size(self) -> int:
        """Get current queue size.
        
        Returns:
            Queue size
        """
        return self.task_queue.qsize()
    
    def get_busy_workers(self) -> int:
        """Get number of busy workers.
        
        Returns:
            Number of busy workers
        """
        return sum(1 for worker in self.workers if worker.is_busy)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_workers": self.num_workers,
            "busy_workers": self.get_busy_workers(),
            "queue_size": self.get_queue_size(),
            "running": self._running
        }


# Global worker pool instance
_translation_pool: Optional[TranslationWorkerPool] = None


def get_translation_pool() -> TranslationWorkerPool:
    """Get global translation worker pool.
    
    Returns:
        TranslationWorkerPool instance
    """
    global _translation_pool
    if _translation_pool is None:
        _translation_pool = TranslationWorkerPool(
            num_workers=settings.translation_workers
        )
    return _translation_pool
