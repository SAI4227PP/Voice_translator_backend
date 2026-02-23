"""
Vosk speech recognition engine.
"""
import json
import asyncio
from typing import Optional, Dict
from pathlib import Path
from app.config import get_logger, get_settings
from app.utils.exceptions import STTError, ModelLoadError

logger = get_logger(__name__)
settings = get_settings()

# Try to import Vosk
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    logger.warning("vosk_not_available", message="Vosk not installed")


class VoskEngine:
    """Vosk speech-to-text engine."""
    
    def __init__(self, model_path: str, sample_rate: int = 16000):
        """Initialize Vosk engine.
        
        Args:
            model_path: Path to Vosk model directory
            sample_rate: Audio sample rate
            
        Raises:
            ModelLoadError: If model cannot be loaded
        """
        if not VOSK_AVAILABLE:
            raise ModelLoadError("Vosk is not installed. Install with: pip install vosk")
        
        self.model_path = Path(model_path)
        self.sample_rate = sample_rate
        self.model: Optional[Model] = None
        
        # Load model
        self._load_model()
        
        logger.info(
            "vosk_engine_initialized",
            model_path=str(model_path),
            sample_rate=sample_rate
        )
    
    def _load_model(self) -> None:
        """Load Vosk model.
        
        Raises:
            ModelLoadError: If model cannot be loaded
        """
        try:
            if not self.model_path.exists():
                raise ModelLoadError(f"Model path does not exist: {self.model_path}")
            
            self.model = Model(str(self.model_path))
            logger.info("vosk_model_loaded", path=str(self.model_path))
        
        except Exception as e:
            logger.error("vosk_model_load_failed", error=str(e), exc_info=True)
            raise ModelLoadError(f"Failed to load Vosk model: {e}")
    
    def create_recognizer(self) -> 'KaldiRecognizer':
        """Create a new recognizer instance.
        
        Returns:
            KaldiRecognizer instance
        """
        if not self.model:
            raise STTError("Model not loaded")
        
        return KaldiRecognizer(self.model, self.sample_rate)
    
    def recognize(self, audio_data: bytes, recognizer: Optional['KaldiRecognizer'] = None) -> Dict:
        """Recognize speech from audio data.
        
        Args:
            audio_data: Raw audio bytes (PCM16)
            recognizer: Optional existing recognizer instance
            
        Returns:
            Recognition result dictionary
        """
        try:
            if recognizer is None:
                recognizer = self.create_recognizer()
            
            # Process audio
            if recognizer.AcceptWaveform(audio_data):
                result = recognizer.Result()
            else:
                result = recognizer.PartialResult()
            
            return json.loads(result)
        
        except Exception as e:
            logger.error("recognition_failed", error=str(e), exc_info=True)
            raise STTError(f"Speech recognition failed: {e}")
    
    async def recognize_async(
        self,
        audio_data: bytes,
        recognizer: Optional['KaldiRecognizer'] = None
    ) -> Dict:
        """Async wrapper for recognition.
        
        Args:
            audio_data: Raw audio bytes
            recognizer: Optional existing recognizer
            
        Returns:
            Recognition result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.recognize,
            audio_data,
            recognizer
        )
    
    def recognize_stream(self, recognizer: 'KaldiRecognizer') -> Dict:
        """Get current recognition result without feeding new data.
        
        Args:
            recognizer: Recognizer instance
            
        Returns:
            Partial or final result
        """
        try:
            result = recognizer.PartialResult()
            return json.loads(result)
        except Exception as e:
            logger.error("stream_recognition_failed", error=str(e))
            raise STTError(f"Stream recognition failed: {e}")
    
    def finalize(self, recognizer: 'KaldiRecognizer') -> Dict:
        """Get final recognition result.
        
        Args:
            recognizer: Recognizer instance
            
        Returns:
            Final result
        """
        try:
            result = recognizer.FinalResult()
            return json.loads(result)
        except Exception as e:
            logger.error("finalization_failed", error=str(e))
            raise STTError(f"Finalization failed: {e}")
