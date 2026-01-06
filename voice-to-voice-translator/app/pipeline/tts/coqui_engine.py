"""
Coqui TTS engine.
"""
import asyncio
import os
from typing import Optional
from pathlib import Path
import numpy as np
from app.config import get_logger, get_settings
from app.utils.exceptions import TTSError, ModelLoadError

logger = get_logger(__name__)
settings = get_settings()

# Set environment variable to agree to TOS for non-interactive environments
os.environ['COQUI_TOS_AGREED'] = '1'

# Try to import Coqui TTS
try:
    from TTS.api import TTS as CoquiTTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logger.warning("coqui_tts_not_available", message="Coqui TTS not installed")


class CoquiEngine:
    """Coqui TTS engine."""
    
    # Class-level cache for loaded models to enable true warm start
    _model_cache = {}
    
    def __init__(self, model_name: Optional[str] = None, language: str = "en"):
        """Initialize Coqui TTS engine.
        
        Args:
            model_name: TTS model name (e.g., 'tts_models/en/ljspeech/tacotron2-DDC')
            language: Language code
            
        Raises:
            ModelLoadError: If model cannot be loaded
        """
        if not TTS_AVAILABLE:
            raise ModelLoadError(
                "Coqui TTS not installed. Install with: pip install TTS"
            )
        
        self.model_name = model_name or self._get_default_model(language)
        self.language = language
        self.tts: Optional[CoquiTTS] = None
        
        # Load model (uses cache if available for warm start)
        self._load_model()
        
        logger.info(
            "coqui_engine_initialized",
            model_name=self.model_name,
            language=language,
            cached=self.model_name in self._model_cache
        )
    
    def _get_default_model(self, language: str) -> str:
        """Get default model for language.
        
        Args:
            language: Language code
            
        Returns:
            Model name
        """
        # For English and common European languages, use specific models (no TOS required)
        simple_models = {
            "en": "tts_models/en/ljspeech/tacotron2-DDC",
            "es": "tts_models/es/mai/tacotron2-DDC",
            "fr": "tts_models/fr/mai/tacotron2-DDC",
            "de": "tts_models/de/thorsten/tacotron2-DDC",
            "it": "tts_models/it/mai/tacotron2-DDC",
            "pt": "tts_models/pt/cv/vits",
            "ru": "tts_models/ru/multi-dataset/vits",
            "zh": "tts_models/zh-CN/baker/tacotron2-DDC",
            "ja": "tts_models/ja/kokoro/tacotron2-DDC",
        }
        
        # Use simple models in production/non-interactive environments
        # XTTS v2 requires TOS agreement which fails in Docker
        use_simple_models = os.getenv('TTS_USE_SIMPLE_MODELS', 'false').lower() == 'true'
        
        if language in simple_models and (use_simple_models or not os.isatty(0)):
            logger.info(
                "using_simple_tts_model",
                language=language,
                model=simple_models[language],
                reason="non-interactive environment"
            )
            return simple_models[language]
        
        # For Indian languages, use Fairseq MMS models (no TOS required)
        # Fairseq MMS supports 1100+ languages including all major Indian languages
        indian_languages = {
            "hi": "hin",  # Hindi
            "bn": "ben",  # Bengali
            "te": "tel",  # Telugu
            "ta": "tam",  # Tamil
            "mr": "mar",  # Marathi
            "gu": "guj",  # Gujarati
            "kn": "kan",  # Kannada
            "ml": "mal",  # Malayalam
            "pa": "pan",  # Punjabi
            "ur": "urd",  # Urdu
            "as": "asm",  # Assamese
            "or": "ory",  # Odia (Oriya)
        }
        
        if language in indian_languages:
            iso_code = indian_languages[language]
            model_name = f"tts_models/{iso_code}/fairseq/vits"
            logger.info(
                "using_fairseq_tts_model",
                language=language,
                iso_code=iso_code,
                model=model_name
            )
            return model_name
        
        # For other languages in simple_models, use them
        if language in simple_models:
            return simple_models[language]
        
        # Default fallback to English model
        logger.warning(
            "language_not_supported_fallback",
            language=language,
            fallback="en"
        )
        return simple_models["en"]
    
    def _agree_to_tos(self) -> None:
        """Programmatically agree to Coqui TTS Terms of Service.
        
        This is needed for XTTS models in non-interactive environments.
        """
        try:
            # Get TTS cache directory
            cache_dir = Path.home() / ".local" / "share" / "tts"
            
            # For Docker/non-interactive environments, use /tmp
            if not os.access(str(Path.home()), os.W_OK):
                cache_dir = Path("/tmp") / ".local" / "share" / "tts"
            
            # Create model-specific directory
            model_dir = cache_dir / self.model_name.replace("/", "--")
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Create TOS agreement file
            tos_file = model_dir / ".tos_agreed"
            if not tos_file.exists():
                tos_file.write_text(
                    "I have read, understood and agreed to the Terms and Conditions.\n"
                    "Auto-agreed for API usage in production environment.\n"
                )
                logger.info("coqui_tos_agreed", model=self.model_name)
        except Exception as e:
            logger.warning("coqui_tos_agreement_failed", error=str(e))
    
    def _load_model(self) -> None:
        """Load TTS model.
        
        Raises:
            ModelLoadError: If model cannot be loaded
        """
        try:
            # Check if model is already cached (warm start)
            if self.model_name in self._model_cache:
                self.tts = self._model_cache[self.model_name]
                logger.info(
                    "coqui_model_loaded_from_cache",\n                    model=self.model_name,\n                    message=\"Using cached model (warm start)\"\n                )\n                return
            
            # Pre-agree to TOS for XTTS models
            if "xtts" in self.model_name.lower():
                self._agree_to_tos()
            
            # Load model for the first time
            logger.info(\"coqui_model_loading\", model=self.model_name, message=\"Loading model (cold start)\")\n            self.tts = CoquiTTS(model_name=self.model_name, progress_bar=False, gpu=False)\n            \n            # Cache the loaded model for future use (enables warm start)\n            self._model_cache[self.model_name] = self.tts\n            \n            logger.info(\n                \"coqui_model_loaded_and_cached\",\n                model=self.model_name,\n                cache_size=len(self._model_cache)\n            )
        
        except EOFError as e:
            # TOS prompt failed in non-interactive mode
            logger.error(
                "coqui_tos_prompt_failed",
                error="TOS agreement required but running in non-interactive mode",
                model=self.model_name
            )
            raise ModelLoadError(
                f"Failed to load {self.model_name}: TOS agreement required. "
                "Running in non-interactive environment. Please set COQUI_TOS_AGREED=1 "
                "or use a model that doesn't require TOS."
            )
        except Exception as e:
            logger.error(
                "coqui_model_load_failed", 
                error=str(e), 
                model=self.model_name,
                exc_info=True
            )
            raise ModelLoadError(f"Failed to load Coqui TTS model: {e}")
    
    def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None
    ) -> np.ndarray:
        """Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            output_path: Optional path to save audio file
            
        Returns:
            Audio as numpy array
            
        Raises:
            TTSError: If synthesis fails
        """
        if not self.tts:
            raise TTSError("TTS model not loaded")
        
        if not text or not text.strip():
            return np.array([], dtype=np.float32)
        
        try:
            # For XTTS v2 multilingual model, specify language
            if "xtts" in self.model_name.lower():
                # Generate directly to numpy array with language parameter
                audio = self.tts.tts(text=text, language=self.language)
            elif "fairseq" in self.model_name.lower():
                # Fairseq models work without language parameter
                # Directly call tts() for Fairseq models
                audio = self.tts.tts(text=text)
            else:
                # Other models (tacotron2, vits, etc.)
                # These models typically work without language parameter
                audio = self.tts.tts(text=text)
            
            logger.debug(
                "tts_synthesis_complete",
                text_length=len(text),
                audio_length=len(audio) if isinstance(audio, np.ndarray) else 0,
                model=self.model_name,
                language=self.language
            )
            
            return np.array(audio, dtype=np.float32)
        
        except Exception as e:
            logger.error(
                "tts_synthesis_failed", 
                error=str(e), 
                model=self.model_name,
                language=self.language,
                text_preview=text[:50],
                exc_info=True
            )
            raise TTSError(f"TTS synthesis failed for language '{self.language}': {e}")
    
    async def synthesize_async(
        self,
        text: str,
        output_path: Optional[str] = None
    ) -> bytes:
        """Async wrapper for synthesis that returns PCM16 bytes.
        
        Args:
            text: Text to synthesize
            output_path: Optional output path
            
        Returns:
            Audio as PCM16 bytes (suitable for API responses)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.synthesize_to_bytes,
            text
        )
    
    def synthesize_to_bytes(self, text: str) -> bytes:
        """Synthesize speech and return as PCM16 WAV bytes.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio as WAV file bytes (complete with header)
        """
        import io
        import wave
        
        audio = self.synthesize(text)
        
        # Convert float32 to int16
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.get_sample_rate())
            wav_file.writeframes(audio_int16.tobytes())
        
        return wav_buffer.getvalue()
    
    async def synthesize_to_bytes_async(self, text: str) -> bytes:
        """Async version of synthesize_to_bytes.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio as PCM16 bytes
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.synthesize_to_bytes,
            text
        )
    
    def _load_audio(self, path: str) -> np.ndarray:
        """Load audio from file.
        
        Args:
            path: Audio file path
            
        Returns:
            Audio as numpy array
        """
        # Simple wav loading (assuming 16-bit PCM)
        import wave
        with wave.open(path, 'rb') as wav:
            frames = wav.readframes(wav.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16)
            audio = audio.astype(np.float32) / 32767.0
        return audio
    
    def get_sample_rate(self) -> int:
        """Get model sample rate.
        
        Returns:
            Sample rate in Hz
        """
        if not self.tts:
            return settings.audio_sample_rate
        
        # Try to get sample rate from model config
        try:
            return self.tts.synthesizer.output_sample_rate
        except:
            return settings.audio_sample_rate
