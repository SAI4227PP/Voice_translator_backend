"""
Utility to scan and detect available models.
"""
import os
from pathlib import Path
from typing import Dict, List, Set
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
        
        if not base_path.exists():
            logger.warning("stt_models_path_not_found", path=str(base_path))
            return stt_models
        
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
        
        # Scan for vosk model directories
        for item in base_path.iterdir():
            if item.is_dir() and item.name.startswith("vosk-"):
                lang_code = item.name.replace("vosk-", "").split("-")[0]
                if lang_code in language_names:
                    stt_models[lang_code] = {
                        "name": language_names[lang_code],
                        "model": item.name,
                        "path": str(item)
                    }
                    logger.debug("found_stt_model", language=lang_code, model=item.name)
        
        return stt_models
    
    @staticmethod
    def get_available_translation_languages() -> Dict[str, Dict[str, str]]:
        """Get available translation languages based on installed Argos packages.
        
        Returns:
            Dictionary of available translation languages
        """
        translation_langs = {}
        
        try:
            import argostranslate.package
            argostranslate.package.update_package_index()
            installed_packages = argostranslate.package.get_installed_packages()
            
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
                logger.debug(
                    "found_translation_package",
                    from_lang=package.from_code,
                    to_lang=package.to_code
                )
            
            # Build language dictionary
            for lang_code in lang_codes:
                translation_langs[lang_code] = {
                    "name": language_names.get(lang_code, lang_code.upper())
                }
        
        except ImportError:
            logger.warning("argostranslate_not_available")
        except Exception as e:
            logger.error("error_scanning_translation_models", error=str(e), exc_info=True)
        
        return translation_langs
    
    @staticmethod
    def get_available_tts_languages() -> Dict[str, Dict[str, any]]:
        """Get available TTS languages based on Coqui TTS models.
        
        Returns:
            Dictionary of available TTS languages with voices
        """
        tts_models = {}
        
        try:
            from TTS.api import TTS
            
            # Get list of available models
            available_models = TTS.list_models()
            
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
                logger.debug("found_tts_language", language=lang_code, voice_count=len(voices))
        
        except ImportError:
            logger.warning("coqui_tts_not_available")
            # Fallback: check for downloaded models in filesystem
            tts_path = Path(settings.coqui_model_path)
            if tts_path.exists():
                for item in tts_path.iterdir():
                    if item.is_dir():
                        lang_code = item.name.split("_")[0] if "_" in item.name else item.name[:2]
                        tts_models[lang_code] = {
                            "name": lang_code.upper(),
                            "voices": [item.name]
                        }
        except Exception as e:
            logger.error("error_scanning_tts_models", error=str(e), exc_info=True)
        
        return tts_models
    
    @staticmethod
    def get_translation_pairs() -> List[Dict[str, str]]:
        """Get available translation pairs based on installed Argos packages.
        
        Returns:
            List of translation pairs with from/to language codes
        """
        pairs = []
        
        try:
            import argostranslate.package
            argostranslate.package.update_package_index()
            installed_packages = argostranslate.package.get_installed_packages()
            
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
            
            for package in installed_packages:
                from_name = language_names.get(package.from_code, package.from_code.upper())
                to_name = language_names.get(package.to_code, package.to_code.upper())
                
                pairs.append({
                    "from": package.from_code,
                    "to": package.to_code,
                    "name": f"{from_name} → {to_name}"
                })
                logger.debug(
                    "found_translation_pair",
                    from_lang=package.from_code,
                    to_lang=package.to_code
                )
        
        except ImportError:
            logger.warning("argostranslate_not_available_for_pairs")
        except Exception as e:
            logger.error("error_getting_translation_pairs", error=str(e), exc_info=True)
        
        return pairs
