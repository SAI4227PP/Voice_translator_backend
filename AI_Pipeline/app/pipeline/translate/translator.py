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
    
    async def _ensure_package_installed(
        self,
        source_lang: str,
        target_lang: str
    ) -> bool:
        """Auto-install translation package if not available.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            True if package is available or was installed successfully
        """
        if not self.engine:
            return False
        
        # Check if already available
        if self.engine.is_language_pair_available(source_lang, target_lang):
            return True
        
        logger.info(
            "auto_installing_translation_package",
            source=source_lang,
            target=target_lang
        )
        
        try:
            # Install the package
            success = await self.engine.install_language_pair(source_lang, target_lang)
            
            if success:
                logger.info(
                    "translation_package_installed",
                    source=source_lang,
                    target=target_lang
                )
            else:
                logger.warning(
                    "translation_package_install_failed",
                    source=source_lang,
                    target=target_lang
                )
            
            return success
        except Exception as e:
            logger.error(
                "translation_package_install_error",
                source=source_lang,
                target=target_lang,
                error=str(e)
            )
            return False
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """Translate text with automatic bridge language support via English.
        
        Uses English as a universal bridge language for any language pair.
        Tries direct translation first, then falls back to bridge translation.
        
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
        
        # Skip if source and target are the same
        if source_lang == target_lang:
            logger.info("same_language_skipping_translation", lang=source_lang)
            return text
        
        # Try to auto-install direct translation package
        if not self.engine.is_language_pair_available(source_lang, target_lang):
            logger.info(
                "package_not_found_attempting_install",
                source=source_lang,
                target=target_lang
            )
            installed = await self._ensure_package_installed(source_lang, target_lang)
            
            if installed:
                logger.info(
                    "package_installed_will_use",
                    source=source_lang,
                    target=target_lang
                )
        
        # Check if direct translation is available (after potential install)
        if self.engine.is_language_pair_available(source_lang, target_lang):
            logger.info(
                "direct_translation",
                source=source_lang,
                target=target_lang
            )
            return await self.engine.translate_async(text, source_lang, target_lang)
        
        # If direct translation not available, try bridge via English for ALL language pairs
        # Skip bridge if source or target is already English
        if source_lang != "en" and target_lang != "en":
            logger.info(
                "attempting_bridge_translation_via_english",
                source=source_lang,
                target=target_lang
            )
            
            # Try to install bridge packages if not available
            if not self.engine.is_language_pair_available(source_lang, "en"):
                logger.info("installing_bridge_package_source_to_en", source=source_lang)
                await self._ensure_package_installed(source_lang, "en")
            
            if not self.engine.is_language_pair_available("en", target_lang):
                logger.info("installing_bridge_package_en_to_target", target=target_lang)
                await self._ensure_package_installed("en", target_lang)
            
            # Check if bridge is possible
            if (self.engine.is_language_pair_available(source_lang, "en") and
                    self.engine.is_language_pair_available("en", target_lang)):
                
                logger.info("using_bridge_translation", source=source_lang, target=target_lang)
                
                # Two-step translation: source→English→target
                english_text = await self.engine.translate_async(text, source_lang, "en")
                logger.debug("bridge_step_1_complete", source=source_lang, english_preview=english_text[:50])
                
                final_text = await self.engine.translate_async(english_text, "en", target_lang)
                logger.debug("bridge_step_2_complete", target=target_lang, result_preview=final_text[:50])
                
                return final_text
        
        # Log detailed info about what packages are available
        logger.warning(
            "no_translation_path_found",
            source=source_lang,
            target=target_lang,
            message=f"Could not find or install translation for {source_lang}→{target_lang}"
        )
        
        # If no translation path available after installation attempts
        raise UnsupportedLanguageError(
            f"Language pair {source_lang}→{target_lang} not available and could not be installed. "
            f"Package may not exist in Argos Translate repository."
        )
    
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
    
    def warm_up(self) -> None:
        """Warm up translation models by preloading all installed packages.
        
        Delegates to the underlying engine's warm_up method.
        """
        if self.engine:
            self.engine.warm_up()
    
    def warm_up_common_pairs(self, pairs: list[tuple[str, str]]) -> None:
        """Warm up only common language pairs.
        
        Args:
            pairs: List of (source, target) language code tuples
            
        Delegates to the underlying engine's warm_up_common_pairs method.
        """
        if self.engine:
            self.engine.warm_up_common_pairs(pairs)


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
