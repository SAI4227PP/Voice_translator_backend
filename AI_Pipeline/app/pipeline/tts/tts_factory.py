"""
TTS engine factory.
"""
from typing import Optional
from app.config import get_logger, get_settings
from app.pipeline.tts.coqui_engine import CoquiEngine
from app.utils.exceptions import ConfigurationError

logger = get_logger(__name__)
settings = get_settings()


class TTSFactory:
    """Factory for creating TTS engine instances."""
    
    _engines = {}
    
    @classmethod
    def create(
        cls,
        engine_type: str = "coqui",
        language: str = "en",
        model_name: Optional[str] = None
    ) -> CoquiEngine:
        """Create TTS engine instance.
        
        Args:
            engine_type: Type of TTS engine (currently only 'coqui')
            language: Language code
            model_name: Optional specific model name
            
        Returns:
            TTS engine instance
            
        Raises:
            ConfigurationError: If engine type not supported
        """
        cache_key = f"{engine_type}_{language}_{model_name or 'default'}"
        
        # Return cached engine if available
        if cache_key in cls._engines:
            logger.debug("returning_cached_tts_engine", key=cache_key)
            return cls._engines[cache_key]
        
        # Create new engine
        if engine_type.lower() == "coqui":
            engine = CoquiEngine(model_name=model_name, language=language)
            cls._engines[cache_key] = engine
            return engine
        
        else:
            raise ConfigurationError(f"Unsupported TTS engine: {engine_type}")
    
    @classmethod
    def get_engine(cls, language: str = "en") -> CoquiEngine:
        """Get TTS engine for language.
        
        Args:
            language: Language code
            
        Returns:
            TTS engine instance
        """
        return cls.create(settings.tts_engine, language)
    
    @classmethod
    def preload_engines(cls, languages: list[str]) -> dict[str, bool]:
        """Preload TTS engines for multiple languages (warm start).
        
        This method loads TTS models at startup to avoid cold start delays
        when processing the first request for each language.
        
        Args:
            languages: List of language codes to preload
            
        Returns:
            Dictionary mapping language codes to success status
        """
        results = {}
        
        for language in languages:
            try:
                # Create engine (will be cached automatically)
                engine = cls.create(settings.tts_engine, language)
                results[language] = True
                logger.info("tts_engine_preloaded", language=language)
            except Exception as e:
                results[language] = False
                logger.error(
                    "tts_engine_preload_failed",
                    language=language,
                    error=str(e),
                    exc_info=True
                )
        
        logger.info(
            "tts_preload_complete",
            total=len(languages),
            success=sum(results.values()),
            failed=len(languages) - sum(results.values())
        )
        
        return results
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached engines."""
        cls._engines.clear()
        logger.info("tts_engine_cache_cleared")
