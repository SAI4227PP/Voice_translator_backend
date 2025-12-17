"""Utils module initialization."""
from app.utils.exceptions import *
from app.utils.timers import (
    Timer,
    time_block,
    PerformanceTracker,
    performance_tracker,
    get_performance_tracker
)
from app.utils.logger import (
    log_function_call,
    log_error_with_context,
    create_component_logger
)

__all__ = [
    # Exceptions
    "VoiceTranslatorException",
    "ConfigurationError",
    "ModelLoadError",
    "STTError",
    "TranslationError",
    "TTSError",
    "AudioProcessingError",
    "RoomError",
    "RoomFullError",
    "RoomNotFoundError",
    "UserNotFoundError",
    "ConnectionError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "UnsupportedLanguageError",
    "PipelineError",
    # Timers
    "Timer",
    "time_block",
    "PerformanceTracker",
    "performance_tracker",
    "get_performance_tracker",
    # Logger
    "log_function_call",
    "log_error_with_context",
    "create_component_logger",
]
