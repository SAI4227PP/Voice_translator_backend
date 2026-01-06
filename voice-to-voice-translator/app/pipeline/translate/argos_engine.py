"""
Argos Translate translation engine.
"""
import asyncio
from typing import Optional
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

# Global spaCy model cache (loaded once, shared across all instances)
_spacy_model = None
_spacy_load_attempted = False

def get_spacy_model():
    """Get or load spaCy model (cached, loaded only once).
    
    Returns:
        Loaded spaCy model or None if unavailable
    """
    global _spacy_model, _spacy_load_attempted
    
    if _spacy_load_attempted:
        return _spacy_model
    
    _spacy_load_attempted = True
    
    try:
        import spacy
        _spacy_model = spacy.load("xx_sent_ud_sm")
        logger.info("spacy_xx_model_loaded_and_cached")
        return _spacy_model
    except (OSError, ImportError) as e:
        logger.warning(
            "spacy_xx_model_load_failed",
            error=str(e),
            message="Continuing without spaCy sentence segmentation"
        )
        return None


class ArgosEngine:
    """Argos Translate translation engine."""
    
    # Class-level translation cache for extreme speed
    _translation_cache = {}
    _cache_max_size = 1000
    _cache_hits = 0
    _cache_misses = 0
    
    # Pre-compiled translation pipelines for faster access
    _translation_pipelines = {}
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text to improve cache hit rate."""
        # Remove extra whitespace, normalize line endings
        return ' '.join(text.strip().split())
    
    def __init__(self):
        """Initialize Argos engine.
        
        Raises:
            ModelLoadError: If Argos not available
        """
        if not ARGOS_AVAILABLE:
            raise ModelLoadError(
                "Argos Translate not installed. Install with: pip install argostranslate"
            )

        # Get cached spaCy model (loaded once globally, not per instance)
        get_spacy_model()
        
        # Only get installed packages, do not update package index
        try:
            self.installed_languages = argostranslate.package.get_installed_packages()
            
            # Pre-build translation pipelines for all installed language pairs
            self._build_translation_pipelines()
            
            logger.info(
                "argos_engine_initialized",
                installed_packages=len(self.installed_languages),
                cached_pipelines=len(self._translation_pipelines)
            )
        except Exception as e:
            logger.error("argos_init_failed", error=str(e), exc_info=True)
            raise ModelLoadError(f"Failed to initialize Argos: {e}")
        
        self._warmed_up = False
    
    def _build_translation_pipelines(self):
        """Pre-build translation pipelines for faster access."""
        for package in self.installed_languages:
            key = f"{package.from_code}_{package.to_code}"
            if key not in self._translation_pipelines:
                # Get the translation pipeline
                pipeline = argostranslate.translate.get_translation_from_codes(
                    package.from_code,
                    package.to_code
                )
                if pipeline:
                    self._translation_pipelines[key] = pipeline
        
        logger.debug(
            "translation_pipelines_built",
            count=len(self._translation_pipelines)
        )
    
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
        
        # Normalize text for better cache hits
        normalized_text = self._normalize_text(text)
        
        # Check class-level cache first (much faster than lru_cache)
        cache_key = f"{source_lang}:{target_lang}:{normalized_text}"
        if cache_key in self._translation_cache:
            self.__class__._cache_hits += 1
            logger.debug(
                "translation_cache_hit",
                text_preview=text[:30],
                hit_rate=f"{self._cache_hits}/{self._cache_hits + self._cache_misses}"
            )
            return self._translation_cache[cache_key]
        
        self.__class__._cache_misses += 1
        
        try:
            # Use pre-built pipeline if available (much faster)
            pipeline_key = f"{source_lang}_{target_lang}"
            if pipeline_key in self._translation_pipelines:
                translated = self._translation_pipelines[pipeline_key].translate(normalized_text)
            else:
                # Fallback to standard translate (slower, rebuilds pipeline)
                translated = argostranslate.translate.translate(
                    normalized_text,
                    source_lang,
                    target_lang
                )
            
            # Smart caching: cache more aggressively for short texts
            should_cache = (
                (len(normalized_text) < 200) or  # Short texts
                (self._cache_misses % 10 == 0)   # Every 10th miss for longer texts
            )
            
            if should_cache and len(self._translation_cache) < self._cache_max_size:
                self._translation_cache[cache_key] = translated
            elif len(self._translation_cache) >= self._cache_max_size:
                # Simple FIFO eviction: remove oldest entry
                oldest_key = next(iter(self._translation_cache))
                del self._translation_cache[oldest_key]
                self._translation_cache[cache_key] = translated
            
            logger.debug(
                "translation_complete",
                source_lang=source_lang,
                target_lang=target_lang,
                original_length=len(text),
                translated_length=len(translated),
                used_pipeline=pipeline_key in self._translation_pipelines
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
        # Since translate() is already heavily cached and uses pre-built pipelines,
        # call it directly instead of using run_in_executor (reduces overhead)
        # Translation is fast enough (~50-200ms) to not block the event loop
        return self.translate(text, source_lang, target_lang)
    
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
        """Async batch translation with optimized processing.
        
        Args:
            texts: List of texts
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            List of translations
        """
        # Use list comprehension for cached translations (instant)
        # This is much faster than creating tasks for already-cached items
        results = []
        for text in texts:
            results.append(self.translate(text, source_lang, target_lang))
        return results
    
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
        # Add guard to prevent repeated install attempts
        if self.is_language_pair_available(source_lang, target_lang):
            logger.info(
                "install_language_pair_skipped",
                source=source_lang,
                target=target_lang,
                reason="already installed"
            )
            return True
        try:
            logger.info(
                "installing_translation_package",
                source=source_lang,
                target=target_lang
            )
            
            # Update package index only here
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
            
            # Rebuild translation pipelines with new package
            self._build_translation_pipelines()
            
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
        self._translation_cache.clear()
        logger.info(
            "translation_cache_cleared",
            previous_size=len(self._translation_cache)
        )

    def warm_up(self) -> None:
        """Warm up translation models by running a dummy translation for each installed language pair."""
        if self._warmed_up:
            logger.info("argos_warmup_skipped", reason="already warmed up")
            return
        import time
        start = time.time()
        try:
            for package in self.installed_languages:
                # Run a dummy translation to load the model into memory
                argostranslate.translate.translate(
                    "hello",
                    package.from_code,
                    package.to_code
                )
            self._warmed_up = True
            logger.info(
                "argos_models_warmed_up",
                total_packages=len(self.installed_languages),
                warmup_time=round(time.time() - start, 2)
            )
        except Exception as e:
            logger.warning(
                "argos_warmup_failed",
                error=str(e),
                exc_info=True
            )

    def warm_up_common_pairs(self, pairs: list[tuple[str, str]]) -> None:
        """Warm up only common language pairs, skipping unavailable pairs."""
        if self._warmed_up:
            logger.info("argos_common_warmup_skipped", reason="already warmed up")
            return
        import time
        start = time.time()
        try:
            warmed = 0
            for src, tgt in pairs:
                if not self.is_language_pair_available(src, tgt):
                    logger.warning(
                        "warmup_pair_not_installed",
                        source=src,
                        target=tgt
                    )
                    continue
                argostranslate.translate.translate("hello", src, tgt)
                warmed += 1
            self._warmed_up = True
            logger.info(
                "argos_common_models_warmed_up",
                warmed_pairs=warmed,
                total_requested=len(pairs),
                warmup_time=round(time.time() - start, 2)
            )
        except Exception as e:
            logger.warning(
                "argos_common_warmup_failed",
                error=str(e),
                exc_info=True
            )
