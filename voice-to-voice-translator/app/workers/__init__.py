"""Workers module initialization."""
from app.workers.translation_worker import (
    TranslationWorker,
    TranslationWorkerPool,
    TranslationTask,
    TranslationResult,
    get_translation_pool
)
from app.workers.tts_worker import (
    TTSWorker,
    TTSWorkerPool,
    TTSTask,
    TTSResult,
    get_tts_pool
)

__all__ = [
    "TranslationWorker",
    "TranslationWorkerPool",
    "TranslationTask",
    "TranslationResult",
    "get_translation_pool",
    "TTSWorker",
    "TTSWorkerPool",
    "TTSTask",
    "TTSResult",
    "get_tts_pool",
]
