"""
Custom exceptions for the application.
"""


class VoiceTranslatorException(Exception):
    """Base exception for all application exceptions."""
    pass


class ConfigurationError(VoiceTranslatorException):
    """Configuration related errors."""
    pass


class ModelLoadError(VoiceTranslatorException):
    """Model loading errors."""
    pass


class STTError(VoiceTranslatorException):
    """Speech-to-text errors."""
    pass


class TranslationError(VoiceTranslatorException):
    """Translation errors."""
    pass


class TTSError(VoiceTranslatorException):
    """Text-to-speech errors."""
    pass


class AudioProcessingError(VoiceTranslatorException):
    """Audio processing errors."""
    pass


class RoomError(VoiceTranslatorException):
    """Room management errors."""
    pass


class RoomFullError(RoomError):
    """Room is at maximum capacity."""
    pass


class RoomNotFoundError(RoomError):
    """Room does not exist."""
    pass


class UserNotFoundError(VoiceTranslatorException):
    """User not found."""
    pass


class ConnectionError(VoiceTranslatorException):
    """WebSocket connection errors."""
    pass


class AuthenticationError(VoiceTranslatorException):
    """Authentication errors."""
    pass


class RateLimitError(VoiceTranslatorException):
    """Rate limiting errors."""
    pass


class ValidationError(VoiceTranslatorException):
    """Data validation errors."""
    pass


class UnsupportedLanguageError(VoiceTranslatorException):
    """Unsupported language."""
    pass


class PipelineError(VoiceTranslatorException):
    """Processing pipeline errors."""
    pass
