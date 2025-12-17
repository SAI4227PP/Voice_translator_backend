"""
Coqui TTS engine.
"""
import asyncio
from typing import Optional
from pathlib import Path
import numpy as np
from app.config import get_logger, get_settings
from app.utils.exceptions import TTSError, ModelLoadError

logger = get_logger(__name__)
settings = get_settings()

# Try to import Coqui TTS
try:
    from TTS.api import TTS as CoquiTTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logger.warning("coqui_tts_not_available", message="Coqui TTS not installed")


class CoquiEngine:
    """Coqui TTS engine."""
    
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
        
        # Load model
        self._load_model()
        
        logger.info(
            "coqui_engine_initialized",
            model_name=self.model_name,
            language=language
        )
    
    def _get_default_model(self, language: str) -> str:
        """Get default model for language.
        
        Args:
            language: Language code
            
        Returns:
            Model name
        """
        defaults = {
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
        return defaults.get(language, defaults["en"])
    
    def _load_model(self) -> None:
        """Load TTS model.
        
        Raises:
            ModelLoadError: If model cannot be loaded
        """
        try:
            self.tts = CoquiTTS(model_name=self.model_name, progress_bar=False)
            logger.info("coqui_model_loaded", model=self.model_name)
        
        except Exception as e:
            logger.error("coqui_model_load_failed", error=str(e), exc_info=True)
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
            # Generate audio
            if output_path:
                self.tts.tts_to_file(text=text, file_path=output_path)
                # Load the saved file
                audio = self._load_audio(output_path)
            else:
                # Generate directly to numpy array
                audio = self.tts.tts(text=text)
            
            logger.debug(
                "tts_synthesis_complete",
                text_length=len(text),
                audio_length=len(audio) if isinstance(audio, np.ndarray) else 0
            )
            
            return np.array(audio, dtype=np.float32)
        
        except Exception as e:
            logger.error("tts_synthesis_failed", error=str(e), exc_info=True)
            raise TTSError(f"TTS synthesis failed: {e}")
    
    async def synthesize_async(
        self,
        text: str,
        output_path: Optional[str] = None
    ) -> np.ndarray:
        """Async wrapper for synthesis.
        
        Args:
            text: Text to synthesize
            output_path: Optional output path
            
        Returns:
            Audio numpy array
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.synthesize,
            text,
            output_path
        )
    
    def synthesize_to_bytes(self, text: str) -> bytes:
        """Synthesize speech and return as PCM16 bytes.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio as PCM16 bytes
        """
        audio = self.synthesize(text)
        
        # Convert float32 to int16
        audio_int16 = (audio * 32767).astype(np.int16)
        
        return audio_int16.tobytes()
    
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
