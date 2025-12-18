"""
Argos Translate translation engine.
"""
import asyncio
from typing import Optional
from functools import lru_cache
from app.config import get_logger, get_settings
from app.utils.exceptions import TranslationError, ModelLoadError

logger = get_logger(__name__)
settings = get_settings()

# Try to import Argos Translate
try:
    import argostranslate.package
    import argostranslate.translate
    ARGOS_AVAILABLE = True
except ImportError:
    ARGOS_AVAILABLE = False
    logger.warning("argos_not_available", message="Argos Translate not installed")


class ArgosEngine:
    """Argos Translate translation engine."""
    
    def __init__(self):
        """Initialize Argos engine.
        
        Raises:
            ModelLoadError: If Argos not available
        """
        if not ARGOS_AVAILABLE:
            raise ModelLoadError(
                "Argos Translate not installed. Install with: pip install argostranslate"
            )
        
        # Set environment variables for argos packages location
        import os
        os.environ.setdefault('ARGOS_PACKAGES_DIR', '/app/.argos_packages')
        os.environ.setdefault('HOME', '/tmp')
        os.environ.setdefault('SPACY_HOME', '/tmp')
        os.environ.setdefault('XDG_CACHE_HOME', '/tmp')
        
        # Update package index
        try:
            argostranslate.package.update_package_index()
            self.installed_languages = argostranslate.package.get_installed_packages()
            
            logger.info(
                "argos_engine_initialized",
                installed_packages=len(self.installed_languages)
            )
        except Exception as e:
            logger.error("argos_init_failed", error=str(e), exc_info=True)
            raise ModelLoadError(f"Failed to initialize Argos: {e}")
    
    @lru_cache(maxsize=1000)
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """Translate text from source to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated text
            
        Raises:
            TranslationError: If translation fails
        """
        if not text or not text.strip():
            return text
        
        try:
            translated = argostranslate.translate.translate(
                text,
                source_lang,
                target_lang
            )
            
            logger.debug(
                "translation_complete",
                source_lang=source_lang,
                target_lang=target_lang,
                original_length=len(text),
                translated_length=len(translated)
            )
            
            return translated
        
        except Exception as e:
            logger.error(
                "translation_failed",
                error=str(e),
                source_lang=source_lang,
                target_lang=target_lang,
                exc_info=True
            )
            raise TranslationError(f"Translation failed: {e}")
    
    async def translate_async(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """Async wrapper for translation.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated text
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.translate,
            text,
            source_lang,
            target_lang
        )
    
    def batch_translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str
    ) -> list[str]:
        """Translate multiple texts.
        
        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            List of translated texts
        """
        return [
            self.translate(text, source_lang, target_lang)
            for text in texts
        ]
    
    async def batch_translate_async(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str
    ) -> list[str]:
        """Async batch translation.
        
        Args:
            texts: List of texts
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            List of translations
        """
        tasks = [
            self.translate_async(text, source_lang, target_lang)
            for text in texts
        ]
        return await asyncio.gather(*tasks)
    
    def get_available_languages(self) -> list[str]:
        """Get list of available languages.
        
        Returns:
            List of language codes
        """
        languages = set()
        for package in self.installed_languages:
            languages.add(package.from_code)
            languages.add(package.to_code)
        return sorted(list(languages))
    
    def is_language_pair_available(
        self,
        source_lang: str,
        target_lang: str
    ) -> bool:
        """Check if language pair is available.
        
        Args:
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            True if available
        """
        for package in self.installed_languages:
            if (package.from_code == source_lang and 
                package.to_code == target_lang):
                return True
        return False
    
    async def install_language_pair(
        self,
        source_lang: str,
        target_lang: str
    ) -> bool:
        """Install translation package for language pair.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            True if installation successful
        """
        # Run the blocking installation in an executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._install_language_pair_sync,
            source_lang,
            target_lang
        )
    
    def _install_language_pair_sync(
        self,
        source_lang: str,
        target_lang: str
    ) -> bool:
        """Synchronous installation logic.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            True if installation successful
        """
        try:
            import os
            os.environ.setdefault('ARGOS_PACKAGES_DIR', '/app/.argos_packages')
            os.environ.setdefault('HOME', '/app')
            
            logger.info(
                "installing_translation_package",
                source=source_lang,
                target=target_lang
            )
            
            # Update package index
            argostranslate.package.update_package_index()
            
            # Get available packages
            available_packages = argostranslate.package.get_available_packages()
            
            logger.info(
                "available_packages_count",
                count=len(available_packages),
                source=source_lang,
                target=target_lang
            )
            
            # Find the package for this language pair
            target_package = None
            for package in available_packages:
                if package.from_code == source_lang and package.to_code == target_lang:
                    target_package = package
                    logger.info(
                        "found_package_to_install",
                        source=source_lang,
                        target=target_lang,
                        package_name=package.package_version
                    )
                    break
            
            if not target_package:
                logger.warning(
                    "translation_package_not_found_in_repo",
                    source=source_lang,
                    target=target_lang,
                    message=f"No package found for {source_lang}→{target_lang} in Argos repository"
                )
                return False
            
            # Download and install the package
            logger.info(
                "downloading_translation_package",
                source=source_lang,
                target=target_lang,
                package=target_package.package_version
            )
            
            download_path = target_package.download()
            logger.info("package_downloaded", path=download_path)
            
            argostranslate.package.install_from_path(download_path)
            logger.info("package_installed_from_path", path=download_path)
            
            # Update installed packages list
            self.installed_languages = argostranslate.package.get_installed_packages()
            
            # Clear translation cache since new packages are available
            self.clear_cache()
            
            logger.info(
                "translation_package_installed_successfully",
                source=source_lang,
                target=target_lang,
                total_packages=len(self.installed_languages)
            )
            
            return True
            
        except PermissionError as e:
            logger.error(
                "permission_error_installing_package",
                source=source_lang,
                target=target_lang,
                error=str(e),
                exc_info=True
            )
            return False
        except Exception as e:
            logger.error(
                "failed_to_install_translation_package",
                source=source_lang,
                target=target_lang,
                error=str(e),
                exc_info=True
            )
            return False
    
    def clear_cache(self) -> None:
        """Clear translation cache."""
        self.translate.cache_clear()
        logger.info("translation_cache_cleared")
