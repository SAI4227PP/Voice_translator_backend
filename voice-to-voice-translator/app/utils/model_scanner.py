"""
Utility to scan and detect available models.
"""
import os
from pathlib import Path
from typing import Dict, List, Set, Any
from app.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


class ModelScanner:
    """Scanner for detecting available models."""
    
    @staticmethod
    def get_available_stt_languages() -> Dict[str, Dict[str, str]]:
        """Get available STT languages based on installed Vosk models.
        
        Returns:
            Dictionary of available STT languages with metadata
        """
        stt_models = {}
        base_path = Path(settings.vosk_model_base_path)
        
        logger.info("scanning_stt_models", path=str(base_path), exists=base_path.exists())
        
        if not base_path.exists():
            logger.warning("stt_models_path_not_found", path=str(base_path))
            # Return default languages when models directory doesn't exist (all configured languages)
            default_stt = {
                "en": {"name": "English", "model": "vosk-en", "path": "models/stt/vosk-en"},
                "hi": {"name": "Hindi", "model": "vosk-hi", "path": "models/stt/vosk-hi"},
                "te": {"name": "Telugu", "model": "vosk-te", "path": "models/stt/vosk-te"},
                "ta": {"name": "Tamil", "model": "vosk-ta", "path": "models/stt/vosk-ta"},
                "kn": {"name": "Kannada", "model": "vosk-kn", "path": "models/stt/vosk-kn"},
                "ml": {"name": "Malayalam", "model": "vosk-ml", "path": "models/stt/vosk-ml"},
                "gu": {"name": "Gujarati", "model": "vosk-gu", "path": "models/stt/vosk-gu"},
                "mr": {"name": "Marathi", "model": "vosk-mr", "path": "models/stt/vosk-mr"},
                "bn": {"name": "Bengali", "model": "vosk-bn", "path": "models/stt/vosk-bn"},
            }
            logger.info("using_default_stt_languages", count=len(default_stt))
            return default_stt
        
        # Language name mappings
        language_names = {
            "en": "English",
            "hi": "Hindi",
            "te": "Telugu",
            "ta": "Tamil",
            "kn": "Kannada",
            "ml": "Malayalam",
            "gu": "Gujarati",
            "mr": "Marathi",
            "bn": "Bengali",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "ru": "Russian",
            "it": "Italian",
            "pt": "Portuguese",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
        }
        
        try:
            # Scan for vosk model directories
            items_found = list(base_path.iterdir())
            logger.info("stt_directory_items", count=len(items_found), items=[i.name for i in items_found])
            
            for item in items_found:
                if item.is_dir() and item.name.startswith("vosk-"):
                    lang_code = item.name.replace("vosk-", "").split("-")[0]
                    if lang_code in language_names:
                        stt_models[lang_code] = {
                            "name": language_names[lang_code],
                            "model": item.name,
                            "path": str(item)
                        }
                        logger.info("found_stt_model", language=lang_code, model=item.name)
        except Exception as e:
            logger.error("error_scanning_stt_directory", error=str(e), exc_info=True)
        
        # If no models found after scanning, return defaults
        if not stt_models:
            logger.warning("no_stt_models_found_using_defaults")
            default_stt = {
                "en": {"name": "English", "model": "vosk-en", "path": "models/stt/vosk-en"},
                "hi": {"name": "Hindi", "model": "vosk-hi", "path": "models/stt/vosk-hi"},
                "te": {"name": "Telugu", "model": "vosk-te", "path": "models/stt/vosk-te"},
                "ta": {"name": "Tamil", "model": "vosk-ta", "path": "models/stt/vosk-ta"},
                "kn": {"name": "Kannada", "model": "vosk-kn", "path": "models/stt/vosk-kn"},
                "ml": {"name": "Malayalam", "model": "vosk-ml", "path": "models/stt/vosk-ml"},
                "gu": {"name": "Gujarati", "model": "vosk-gu", "path": "models/stt/vosk-gu"},
                "mr": {"name": "Marathi", "model": "vosk-mr", "path": "models/stt/vosk-mr"},
                "bn": {"name": "Bengali", "model": "vosk-bn", "path": "models/stt/vosk-bn"},
            }
            return default_stt
        
        logger.info("stt_scan_complete", models_found=len(stt_models))
        return stt_models
    
    @staticmethod
    def get_available_translation_languages() -> Dict[str, Dict[str, str]]:
        """Get available translation languages based on installed Argos packages.
        
        Returns:
            Dictionary of available translation languages
        """
        translation_langs = {}
        
        logger.info("scanning_translation_packages")
        
        try:
            # Set argostranslate to use persisted directory
            import os
            os.environ.setdefault('ARGOS_PACKAGES_DIR', '/app/.argos_packages')
            os.environ.setdefault('HOME', '/app')
            
            import argostranslate.package
            
            # Try to update package index, but don't fail if we can't
            try:
                argostranslate.package.update_package_index()
            except (PermissionError, OSError) as e:
                logger.warning("cannot_update_package_index", error=str(e))
            
            installed_packages = argostranslate.package.get_installed_packages()
            
            logger.info("translation_packages_found", count=len(installed_packages))
            
            # Language name mappings
            language_names = {
                "en": "English",
                "hi": "Hindi",
                "te": "Telugu",
                "ta": "Tamil",
                "es": "Spanish",
                "fr": "French",
                "de": "German",
                "it": "Italian",
                "pt": "Portuguese",
                "ru": "Russian",
                "zh": "Chinese",
                "ja": "Japanese",
                "ko": "Korean",
                "ar": "Arabic",
                "nl": "Dutch",
                "pl": "Polish",
                "tr": "Turkish",
            }
            
            # Collect unique language codes from installed packages
            lang_codes: Set[str] = set()
            for package in installed_packages:
                lang_codes.add(package.from_code)
                lang_codes.add(package.to_code)
                logger.info(
                    "found_translation_package",
                    from_lang=package.from_code,
                    to_lang=package.to_code
                )
            
            # Build language dictionary
            for lang_code in lang_codes:
                translation_langs[lang_code] = {
                    "name": language_names.get(lang_code, lang_code.upper())
                }
            
            # If no packages found, return default languages
            if not translation_langs:
                logger.warning(
                    "no_translation_packages_installed_using_defaults",
                    message="No translation packages installed. Returning default languages. Run download_models.py to install packages."
                )
                # Return default translation languages
                translation_langs = {
                    "en": {"name": "English"},
                    "hi": {"name": "Hindi"},
                    "es": {"name": "Spanish"},
                    "fr": {"name": "French"},
                    "de": {"name": "German"},
                    "te": {"name": "Telugu"},
                    "ta": {"name": "Tamil"},
                }
        
        except ImportError:
            logger.warning("argostranslate_not_available_using_defaults")
            # Return default languages when argostranslate is not available
            return {
                "en": {"name": "English"},
                "hi": {"name": "Hindi"},
                "es": {"name": "Spanish"},
                "fr": {"name": "French"},
            }
        except PermissionError as e:
            logger.error("permission_error_scanning_translation_using_defaults", error=str(e))
            # Return default languages on permission error
            return {
                "en": {"name": "English"},
                "hi": {"name": "Hindi"},
                "es": {"name": "Spanish"},
            }
        except Exception as e:
            logger.error("error_scanning_translation_models_using_defaults", error=str(e), exc_info=True)
            # Return default languages including installed packages
            return {
                "en": {"name": "English"},
                "hi": {"name": "Hindi"},
                "bn": {"name": "Bengali"},
                "es": {"name": "Spanish"},
                "fr": {"name": "French"},
            }
        
        logger.info("translation_scan_complete", languages_found=len(translation_langs))
        return translation_langs
    
    @staticmethod
    def get_available_tts_languages() -> Dict[str, Dict[str, Any]]:
        """Get available TTS languages based on Coqui TTS models.
        
        Returns:
            Dictionary of available TTS languages with voices
        """
        tts_models = {}
        
        logger.info("scanning_tts_models")
        
        try:
            # Disable numba cache to avoid librosa caching errors
            import os
            os.environ['NUMBA_CACHE_DIR'] = '/tmp/numba_cache'
            os.environ.setdefault('NUMBA_DISABLE_JIT', '0')
            os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'
            os.environ['FONTCONFIG_PATH'] = '/tmp/fontconfig'
            
            from TTS.utils.manage import ModelManager
            
            # Get list of available models using ModelManager
            manager = ModelManager()
            available_models = manager.list_models()
            logger.info("tts_available_models", count=len(available_models))
            
            # Language name mappings
            language_names = {
                "en": "English",
                "es": "Spanish",
                "fr": "French",
                "de": "German",
                "it": "Italian",
                "pt": "Portuguese",
                "pl": "Polish",
                "tr": "Turkish",
                "ru": "Russian",
                "nl": "Dutch",
                "cs": "Czech",
                "ar": "Arabic",
                "zh": "Chinese",
                "ja": "Japanese",
                "ko": "Korean",
                "hi": "Hindi",
            }
            
            # Extract language codes from model names
            lang_voices: Dict[str, List[str]] = {}
            for model in available_models:
                # Extract language code from model name (e.g., "tts_models/en/ljspeech/...")
                parts = model.split("/")
                if len(parts) >= 2 and parts[0] == "tts_models":
                    lang_code = parts[1]
                    if lang_code not in lang_voices:
                        lang_voices[lang_code] = []
                    lang_voices[lang_code].append(model)
            
            # Build TTS language dictionary
            for lang_code, voices in lang_voices.items():
                tts_models[lang_code] = {
                    "name": language_names.get(lang_code, lang_code.upper()),
                    "voices": voices[:5]  # Limit to first 5 voices
                }
                logger.info("found_tts_language", language=lang_code, voice_count=len(voices))
        
        except ImportError:
            logger.warning("coqui_tts_not_available")
            # Fallback: check for downloaded models in filesystem
            tts_path = Path(settings.coqui_model_path)
            logger.info("checking_tts_filesystem", path=str(tts_path), exists=tts_path.exists())
            
            if tts_path.exists():
                try:
                    for item in tts_path.iterdir():
                        if item.is_dir():
                            lang_code = item.name.split("_")[0] if "_" in item.name else item.name[:2]
                            tts_models[lang_code] = {
                                "name": lang_code.upper(),
                                "voices": [item.name]
                            }
                            logger.info("found_tts_model_filesystem", language=lang_code, model=item.name)
                except Exception as e:
                    logger.error("error_reading_tts_directory", error=str(e))
        except RuntimeError as e:
            # Handle numba caching errors
            if "cannot cache function" in str(e):
                logger.warning("tts_numba_caching_error_using_fallback", error=str(e))
                # Return empty dict - models need to be downloaded manually
                return {}
            else:
                raise
        except Exception as e:
            logger.error("error_scanning_tts_models", error=str(e), exc_info=True)
            return {}
        
        logger.info("tts_scan_complete", models_found=len(tts_models))
        return tts_models
    
    @staticmethod
    def get_translation_pairs() -> List[Dict[str, str]]:
        """Get available translation pairs based on installed Argos packages.
        
        Returns:
            List of translation pairs with from/to language codes
        """
        pairs = []
        
        logger.info("scanning_translation_pairs")
        
        try:
            # Set argostranslate to use persisted directory
            import os
            os.environ.setdefault('ARGOS_PACKAGES_DIR', '/app/.argos_packages')
            os.environ.setdefault('HOME', '/app')
            
            import argostranslate.package
            
            # Try to update package index, but don't fail if we can't
            try:
                argostranslate.package.update_package_index()
            except (PermissionError, OSError) as e:
                logger.warning("cannot_update_package_index_pairs", error=str(e))
            
            installed_packages = argostranslate.package.get_installed_packages()
            
            logger.info("translation_pairs_packages_found", count=len(installed_packages))
            
            # Language name mappings
            language_names = {
                "en": "English",
                "hi": "Hindi",
                "te": "Telugu",
                "ta": "Tamil",
                "kn": "Kannada",
                "ml": "Malayalam",
                "gu": "Gujarati",
                "mr": "Marathi",
                "bn": "Bengali",
                "es": "Spanish",
                "fr": "French",
                "de": "German",
                "it": "Italian",
                "pt": "Portuguese",
                "ru": "Russian",
                "zh": "Chinese",
                "ja": "Japanese",
                "ko": "Korean",
                "ar": "Arabic",
                "nl": "Dutch",
                "pl": "Polish",
                "tr": "Turkish",
            }
            
            for package in installed_packages:
                from_name = language_names.get(package.from_code, package.from_code.upper())
                to_name = language_names.get(package.to_code, package.to_code.upper())
                
                pairs.append({
                    "from": package.from_code,
                    "to": package.to_code,
                    "name": f"{from_name} → {to_name}"
                })
                logger.info(
                    "found_translation_pair",
                    from_lang=package.from_code,
                    to_lang=package.to_code
                )
            
            # If no packages found, return default pairs
            if not pairs:
                logger.warning(
                    "no_translation_pairs_installed_using_defaults",
                    message="No translation packages installed. Returning default pairs. Run download_models.py to install packages."
                )
                # Return default translation pairs for common languages
                default_pairs = [
                    {"from": "en", "to": "es", "name": "English → Spanish"},
                    {"from": "es", "to": "en", "name": "Spanish → English"},
                    {"from": "en", "to": "fr", "name": "English → French"},
                    {"from": "fr", "to": "en", "name": "French → English"},
                    {"from": "en", "to": "de", "name": "English → German"},
                    {"from": "de", "to": "en", "name": "German → English"},
                    {"from": "en", "to": "hi", "name": "English → Hindi"},
                    {"from": "hi", "to": "en", "name": "Hindi → English"},
                    {"from": "en", "to": "te", "name": "English → Telugu"},
                    {"from": "te", "to": "en", "name": "Telugu → English"},
                    {"from": "en", "to": "ta", "name": "English → Tamil"},
                    {"from": "ta", "to": "en", "name": "Tamil → English"},
                ]
                return default_pairs
        
        except ImportError:
            logger.warning("argostranslate_not_available_for_pairs_using_defaults")
            # Return default pairs even when argostranslate is not available
            return [
                {"from": "en", "to": "es", "name": "English → Spanish"},
                {"from": "es", "to": "en", "name": "Spanish → English"},
                {"from": "en", "to": "fr", "name": "English → French"},
                {"from": "fr", "to": "en", "name": "French → English"},
                {"from": "en", "to": "de", "name": "English → German"},
                {"from": "de", "to": "en", "name": "German → English"},
                {"from": "en", "to": "hi", "name": "English → Hindi"},
                {"from": "hi", "to": "en", "name": "Hindi → English"},
            ]
        except PermissionError as e:
            logger.error("permission_error_getting_pairs_using_defaults", error=str(e))
            # Return default pairs on permission error
            return [
                {"from": "en", "to": "es", "name": "English → Spanish"},
                {"from": "es", "to": "en", "name": "Spanish → English"},
                {"from": "en", "to": "hi", "name": "English → Hindi"},
                {"from": "hi", "to": "en", "name": "Hindi → English"},
                {"from": "en", "to": "bn", "name": "English → Bengali"},
                {"from": "bn", "to": "en", "name": "Bengali → English"},
            ]
        except Exception as e:
            logger.error("error_getting_translation_pairs_using_defaults", error=str(e), exc_info=True)
            # Return default pairs including installed packages
            return [
                {"from": "en", "to": "es", "name": "English → Spanish"},
                {"from": "es", "to": "en", "name": "Spanish → English"},
                {"from": "en", "to": "hi", "name": "English → Hindi"},
                {"from": "hi", "to": "en", "name": "Hindi → English"},
                {"from": "en", "to": "bn", "name": "English → Bengali"},
                {"from": "bn", "to": "en", "name": "Bengali → English"},
            ]
        
        logger.info("translation_pairs_scan_complete", pairs_found=len(pairs))
        return pairs
