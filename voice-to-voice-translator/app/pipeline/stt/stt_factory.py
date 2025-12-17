"""
Speech-to-text engine factory.
"""
from typing import Optional
from app.config import get_logger, get_settings
from app.pipeline.stt.vosk_engine import VoskEngine
from app.utils.exceptions import ConfigurationError

logger = get_logger(__name__)
settings = get_settings()


class STTFactory:
    """Factory for creating STT engine instances."""
    
    _engines = {}
    
    @classmethod
    def create(cls, engine_type: str = "vosk", language: str = "en") -> VoskEngine:
        """Create STT engine instance.
        
        Args:
            engine_type: Type of STT engine (currently only 'vosk')
            language: Language code
            
        Returns:
            STT engine instance
            
        Raises:
            ConfigurationError: If engine type not supported
        """
        cache_key = f"{engine_type}_{language}"
        
        # Return cached engine if available
        if cache_key in cls._engines:
            logger.debug("returning_cached_stt_engine", key=cache_key)
            return cls._engines[cache_key]
        
        # Create new engine
        if engine_type.lower() == "vosk":
            model_path = settings.get_vosk_model_path(language)
            engine = VoskEngine(
                model_path=model_path,
                sample_rate=settings.audio_sample_rate
            )
            cls._engines[cache_key] = engine
            return engine
        
        else:
            raise ConfigurationError(f"Unsupported STT engine: {engine_type}")
    
    @classmethod
    def get_engine(cls, language: str = "en") -> VoskEngine:
        """Get STT engine for language.
        
        Args:
            language: Language code
            
        Returns:
            STT engine instance
        """
        return cls.create(settings.stt_engine, language)
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached engines."""
        cls._engines.clear()
        logger.info("stt_engine_cache_cleared")
