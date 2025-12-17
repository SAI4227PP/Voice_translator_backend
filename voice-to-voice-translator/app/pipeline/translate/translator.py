"""
Translation orchestration.
"""
from typing import Optional
from app.config import get_logger, get_settings
from app.pipeline.translate.argos_engine import ArgosEngine
from app.utils.exceptions import ConfigurationError, UnsupportedLanguageError

logger = get_logger(__name__)
settings = get_settings()


class Translator:
    """Translation service."""
    
    def __init__(self):
        """Initialize translator."""
        self.engine: Optional[ArgosEngine] = None
        self._initialize_engine()
    
    def _initialize_engine(self) -> None:
        """Initialize translation engine."""
        try:
            if settings.translation_engine.lower() == "argos":
                self.engine = ArgosEngine()
            else:
                raise ConfigurationError(
                    f"Unsupported translation engine: {settings.translation_engine}"
                )
        except Exception as e:
            logger.error("translator_init_failed", error=str(e), exc_info=True)
            raise
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """Translate text.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated text
            
        Raises:
            UnsupportedLanguageError: If language pair not supported
        """
        if not self.engine:
            raise ConfigurationError("Translation engine not initialized")
        
        # Check if language pair is available
        if not self.engine.is_language_pair_available(source_lang, target_lang):
            raise UnsupportedLanguageError(
                f"Language pair {source_lang}->{target_lang} not available"
            )
        
        return await self.engine.translate_async(text, source_lang, target_lang)
    
    async def batch_translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str
    ) -> list[str]:
        """Translate multiple texts.
        
        Args:
            texts: Texts to translate
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Translated texts
        """
        if not self.engine:
            raise ConfigurationError("Translation engine not initialized")
        
        return await self.engine.batch_translate_async(texts, source_lang, target_lang)
    
    def get_available_languages(self) -> list[str]:
        """Get available languages.
        
        Returns:
            List of language codes
        """
        if not self.engine:
            return []
        return self.engine.get_available_languages()
    
    def is_language_pair_supported(
        self,
        source_lang: str,
        target_lang: str
    ) -> bool:
        """Check if language pair is supported.
        
        Args:
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            True if supported
        """
        if not self.engine:
            return False
        return self.engine.is_language_pair_available(source_lang, target_lang)


# Global translator instance
_translator: Optional[Translator] = None


def get_translator() -> Translator:
    """Get global translator instance.
    
    Returns:
        Translator instance
    """
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator
