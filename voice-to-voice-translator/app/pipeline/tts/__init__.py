"""TTS module initialization."""
from app.pipeline.tts.coqui_engine import CoquiEngine
from app.pipeline.tts.tts_factory import TTSFactory

__all__ = ["CoquiEngine", "TTSFactory"]
