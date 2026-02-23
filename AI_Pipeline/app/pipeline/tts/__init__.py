"""TTS module initialization."""
from app.pipeline.tts.coqui_engine import CoquiEngine
from app.pipeline.tts.tts_factory import TTSFactory

# Singleton instance
_tts_factory = None

def get_tts_factory() -> TTSFactory:
    """Get singleton TTS factory instance.
    
    Returns:
        TTSFactory instance
    """
    global _tts_factory
    if _tts_factory is None:
        _tts_factory = TTSFactory()
    return _tts_factory

__all__ = ["CoquiEngine", "TTSFactory", "get_tts_factory"]
