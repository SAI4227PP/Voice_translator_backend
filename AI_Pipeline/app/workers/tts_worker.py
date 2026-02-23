"""
TTS worker pool for parallel speech synthesis.
"""
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from app.config import get_logger, get_settings
from app.pipeline.tts import TTSFactory
from app.utils.exceptions import WorkerError

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class TTSTask:
    """TTS task."""
    task_id: str
    text: str
    language: str
    user_id: str
    callback: Optional[Any] = None


@dataclass
class TTSResult:
    """TTS result."""
    task_id: str
    text: str
    audio_data: bytes
    language: str
    processing_time_ms: float


class TTSWorker:
    """Worker for processing TTS tasks."""
    
    def __init__(self, worker_id: int):
        """Initialize worker.
        
        Args:
            worker_id: Worker identifier
        """
        self.worker_id = worker_id
        self.tts_engines: Dict[str, Any] = {}
        self.is_busy = False
        self.current_task: Optional[TTSTask] = None
        
        logger.info("tts_worker_initialized", worker_id=worker_id)
    
    def _get_tts_engine(self, language: str):
        """Get or create TTS engine for language.
        
        Args:
            language: Language code
            
        Returns:
            TTS engine
        """
        if language not in self.tts_engines:
            self.tts_engines[language] = TTSFactory.get_engine(language)
        return self.tts_engines[language]
    
    async def process_task(self, task: TTSTask) -> TTSResult:
        """Process TTS task.
        
        Args:
            task: TTS task
            
        Returns:
            TTS result
        """
        import time
        start_time = time.time()
        
        self.is_busy = True
        self.current_task = task
        
        try:
            logger.debug(
                "worker_processing_tts_task",
                worker_id=self.worker_id,
                task_id=task.task_id
            )
            
            # Get TTS engine
            tts_engine = self._get_tts_engine(task.language)
            
            # Synthesize speech
            audio_bytes = await tts_engine.synthesize_to_bytes_async(task.text)
            
            processing_time = (time.time() - start_time) * 1000
            
            result = TTSResult(
                task_id=task.task_id,
                text=task.text,
                audio_data=audio_bytes,
                language=task.language,
                processing_time_ms=processing_time
            )
            
            logger.info(
                "worker_tts_task_complete",
                worker_id=self.worker_id,
                task_id=task.task_id,
                audio_size=len(audio_bytes),
                processing_time_ms=processing_time
            )
            
            return result
        
        finally:
            self.is_busy = False
            self.current_task = None


class TTSWorkerPool:
    """Pool of TTS workers."""
    
    def __init__(self, num_workers: int = 2):
        """Initialize worker pool.
        
        Args:
            num_workers: Number of workers
        """
        self.num_workers = num_workers
        self.workers = [TTSWorker(i) for i in range(num_workers)]
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_tasks = []
        
        logger.info("tts_worker_pool_initialized", workers=num_workers)
    
    async def start(self) -> None:
        """Start worker pool."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker tasks
        for worker in self.workers:
            task = asyncio.create_task(self._worker_loop(worker))
            self._worker_tasks.append(task)
        
        logger.info("tts_worker_pool_started")    
    async def preload_engines(self, languages: list[str]) -> None:
        """Preload TTS engines for specified languages across all workers.
        
        This implements warm start by loading models before any requests arrive,
        eliminating cold start delays on first use.
        
        Args:
            languages: List of language codes to preload
        """
        logger.info(
            "tts_worker_pool_preloading",
            languages=languages,
            workers=self.num_workers
        )
        
        # Preload engines in the first worker (models are cached at class level)
        if self.workers and languages:
            worker = self.workers[0]
            for language in languages:
                try:
                    # Get/create engine - this will cache it
                    worker._get_tts_engine(language)
                    logger.info(
                        "tts_worker_engine_preloaded",
                        worker_id=worker.worker_id,
                        language=language
                    )
                except Exception as e:
                    logger.error(
                        "tts_worker_engine_preload_failed",
                        worker_id=worker.worker_id,
                        language=language,
                        error=str(e),
                        exc_info=True
                    )
        
        logger.info("tts_worker_pool_preload_complete")
    
    async def stop(self) -> None:
        """Stop worker pool."""
        self._running = False
        
        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        self._worker_tasks.clear()
        logger.info("tts_worker_pool_stopped")
    
    async def _worker_loop(self, worker: TTSWorker) -> None:
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
                    "tts_worker_loop_error",
                    worker_id=worker.worker_id,
                    error=str(e),
                    exc_info=True
                )
    
    async def submit_task(self, task: TTSTask) -> None:
        """Submit task to pool.
        
        Args:
            task: TTS task
        """
        await self.task_queue.put(task)
        
        logger.debug(
            "tts_task_submitted",
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
_tts_pool: Optional[TTSWorkerPool] = None


def get_tts_pool() -> TTSWorkerPool:
    """Get global TTS worker pool.
    
    Returns:
        TTSWorkerPool instance
    """
    global _tts_pool
    if _tts_pool is None:
        _tts_pool = TTSWorkerPool(num_workers=settings.tts_workers)
    return _tts_pool
