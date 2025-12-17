"""
PCM audio validation and quality checking.
"""
import numpy as np
from typing import Optional, Dict, Any
from app.config import get_logger
from app.audio.audio_utils import bytes_to_numpy, compute_rms, normalize_audio
from app.utils.exceptions import ValidationError

logger = get_logger(__name__)


class PCMValidator:
    """Validator for PCM audio data."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
        min_duration_ms: float = 10,
        max_duration_ms: float = 10000
    ):
        """Initialize PCM validator.
        
        Args:
            sample_rate: Expected sample rate
            sample_width: Expected bytes per sample
            channels: Expected number of channels
            min_duration_ms: Minimum duration in milliseconds
            max_duration_ms: Maximum duration in milliseconds
        """
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms
        
        # Calculate size constraints
        self.min_size = int(
            (sample_rate * min_duration_ms / 1000) * sample_width * channels
        )
        self.max_size = int(
            (sample_rate * max_duration_ms / 1000) * sample_width * channels
        )
    
    def validate(self, audio_data: bytes) -> Dict[str, Any]:
        """Validate PCM audio data.
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Validation result dictionary
            
        Raises:
            ValidationError: If validation fails
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {}
        }
        
        # Check size
        size = len(audio_data)
        result["info"]["size_bytes"] = size
        
        if size < self.min_size:
            result["valid"] = False
            result["errors"].append(
                f"Audio too short: {size} bytes (min: {self.min_size})"
            )
        
        if size > self.max_size:
            result["valid"] = False
            result["errors"].append(
                f"Audio too long: {size} bytes (max: {self.max_size})"
            )
        
        # Check alignment
        expected_frame_size = self.sample_width * self.channels
        if size % expected_frame_size != 0:
            result["warnings"].append(
                f"Audio size not aligned to frame size ({expected_frame_size} bytes)"
            )
        
        # Check content quality
        try:
            audio_array = bytes_to_numpy(audio_data)
            
            # Check for all zeros
            if np.all(audio_array == 0):
                result["valid"] = False
                result["errors"].append("Audio contains only zeros")
            
            # Check for clipping
            max_value = np.max(np.abs(audio_array))
            if max_value >= 32767:  # PCM16 max
                result["warnings"].append("Audio may be clipped")
            
            # Check RMS level
            rms = compute_rms(audio_array)
            result["info"]["rms"] = float(rms)
            
            if rms < 100:  # Very quiet
                result["warnings"].append(f"Audio very quiet (RMS: {rms:.2f})")
            
            # Check for DC offset
            mean = np.mean(audio_array)
            if abs(mean) > 1000:
                result["warnings"].append(f"DC offset detected: {mean:.2f}")
            
            result["info"]["peak"] = float(max_value)
            result["info"]["mean"] = float(mean)
            
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Failed to analyze audio: {e}")
        
        # Log result
        if not result["valid"]:
            logger.warning("pcm_validation_failed", **result)
        elif result["warnings"]:
            logger.debug("pcm_validation_warnings", **result)
        
        return result
    
    def validate_strict(self, audio_data: bytes) -> None:
        """Validate audio and raise exception if invalid.
        
        Args:
            audio_data: Raw audio bytes
            
        Raises:
            ValidationError: If validation fails
        """
        result = self.validate(audio_data)
        
        if not result["valid"]:
            errors = ", ".join(result["errors"])
            raise ValidationError(f"PCM validation failed: {errors}")
    
    def is_valid(self, audio_data: bytes) -> bool:
        """Check if audio is valid.
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            True if valid, False otherwise
        """
        result = self.validate(audio_data)
        return result["valid"]


def validate_audio_chunk(
    audio_data: bytes,
    sample_rate: int = 16000,
    min_duration_ms: float = 10
) -> bool:
    """Quick validation of audio chunk.
    
    Args:
        audio_data: Audio bytes
        sample_rate: Sample rate
        min_duration_ms: Minimum duration
        
    Returns:
        True if valid
    """
    validator = PCMValidator(
        sample_rate=sample_rate,
        min_duration_ms=min_duration_ms
    )
    return validator.is_valid(audio_data)
