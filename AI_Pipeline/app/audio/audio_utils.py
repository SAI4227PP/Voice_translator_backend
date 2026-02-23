"""
Audio utility functions for format conversion and processing.
"""
import numpy as np
import struct
from typing import Optional, Tuple
from app.config import get_logger
from app.utils.exceptions import AudioProcessingError

logger = get_logger(__name__)


def bytes_to_numpy(audio_bytes: bytes, dtype=np.int16) -> np.ndarray:
    """Convert audio bytes to numpy array.
    
    Args:
        audio_bytes: Raw audio bytes
        dtype: NumPy data type
        
    Returns:
        NumPy array of audio samples
    """
    try:
        return np.frombuffer(audio_bytes, dtype=dtype)
    except Exception as e:
        logger.error("bytes_to_numpy_failed", error=str(e))
        raise AudioProcessingError(f"Failed to convert bytes to numpy: {e}")


def numpy_to_bytes(audio_array: np.ndarray) -> bytes:
    """Convert numpy array to audio bytes.
    
    Args:
        audio_array: NumPy array of audio samples
        
    Returns:
        Raw audio bytes
    """
    try:
        return audio_array.astype(np.int16).tobytes()
    except Exception as e:
        logger.error("numpy_to_bytes_failed", error=str(e))
        raise AudioProcessingError(f"Failed to convert numpy to bytes: {e}")


def normalize_audio(audio_data: np.ndarray) -> np.ndarray:
    """Normalize audio to [-1, 1] range.
    
    Args:
        audio_data: Audio samples
        
    Returns:
        Normalized audio
    """
    if audio_data.dtype == np.int16:
        return audio_data.astype(np.float32) / 32768.0
    elif audio_data.dtype == np.int32:
        return audio_data.astype(np.float32) / 2147483648.0
    return audio_data


def denormalize_audio(audio_data: np.ndarray, dtype=np.int16) -> np.ndarray:
    """Denormalize audio from [-1, 1] to integer range.
    
    Args:
        audio_data: Normalized audio samples
        dtype: Target data type
        
    Returns:
        Denormalized audio
    """
    if dtype == np.int16:
        return (audio_data * 32767.0).astype(np.int16)
    elif dtype == np.int32:
        return (audio_data * 2147483647.0).astype(np.int32)
    return audio_data


def resample_audio(
    audio_data: np.ndarray,
    orig_sr: int,
    target_sr: int
) -> np.ndarray:
    """Resample audio to different sample rate.
    
    Args:
        audio_data: Audio samples
        orig_sr: Original sample rate
        target_sr: Target sample rate
        
    Returns:
        Resampled audio
    """
    if orig_sr == target_sr:
        return audio_data
    
    try:
        # Simple linear interpolation resampling
        duration = len(audio_data) / orig_sr
        target_length = int(duration * target_sr)
        
        indices = np.linspace(0, len(audio_data) - 1, target_length)
        resampled = np.interp(indices, np.arange(len(audio_data)), audio_data)
        
        return resampled.astype(audio_data.dtype)
    
    except Exception as e:
        logger.error(
            "resample_failed",
            error=str(e),
            orig_sr=orig_sr,
            target_sr=target_sr
        )
        raise AudioProcessingError(f"Failed to resample audio: {e}")


def convert_to_mono(audio_data: np.ndarray, num_channels: int = 2) -> np.ndarray:
    """Convert stereo or multi-channel audio to mono.
    
    Args:
        audio_data: Audio samples
        num_channels: Number of channels
        
    Returns:
        Mono audio
    """
    if num_channels == 1:
        return audio_data
    
    # Reshape and average channels
    reshaped = audio_data.reshape(-1, num_channels)
    return reshaped.mean(axis=1).astype(audio_data.dtype)


def apply_gain(audio_data: np.ndarray, gain_db: float) -> np.ndarray:
    """Apply gain to audio.
    
    Args:
        audio_data: Audio samples
        gain_db: Gain in decibels
        
    Returns:
        Audio with gain applied
    """
    gain_linear = 10 ** (gain_db / 20.0)
    return (audio_data * gain_linear).astype(audio_data.dtype)


def compute_rms(audio_data: np.ndarray) -> float:
    """Compute RMS (Root Mean Square) of audio.
    
    Args:
        audio_data: Audio samples
        
    Returns:
        RMS value
    """
    return np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))


def detect_silence(
    audio_data: np.ndarray,
    threshold: float = 0.01,
    sample_rate: int = 16000
) -> bool:
    """Detect if audio is silence.
    
    Args:
        audio_data: Audio samples
        threshold: RMS threshold for silence
        sample_rate: Sample rate
        
    Returns:
        True if audio is silence
    """
    rms = compute_rms(normalize_audio(audio_data))
    return rms < threshold


def trim_silence(
    audio_data: np.ndarray,
    threshold: float = 0.01,
    frame_length: int = 2048
) -> np.ndarray:
    """Trim silence from beginning and end of audio.
    
    Args:
        audio_data: Audio samples
        threshold: RMS threshold
        frame_length: Frame length for analysis
        
    Returns:
        Trimmed audio
    """
    if len(audio_data) < frame_length:
        return audio_data
    
    normalized = normalize_audio(audio_data)
    
    # Find first non-silent frame
    start = 0
    for i in range(0, len(normalized) - frame_length, frame_length):
        frame = normalized[i:i + frame_length]
        if compute_rms(frame) > threshold:
            start = i
            break
    
    # Find last non-silent frame
    end = len(normalized)
    for i in range(len(normalized) - frame_length, 0, -frame_length):
        frame = normalized[i:i + frame_length]
        if compute_rms(frame) > threshold:
            end = i + frame_length
            break
    
    return audio_data[start:end]


def chunk_audio(
    audio_data: bytes,
    chunk_size: int = 4096
) -> list[bytes]:
    """Split audio data into chunks.
    
    Args:
        audio_data: Audio bytes
        chunk_size: Size of each chunk
        
    Returns:
        List of audio chunks
    """
    chunks = []
    for i in range(0, len(audio_data), chunk_size):
        chunks.append(audio_data[i:i + chunk_size])
    return chunks


def calculate_duration(
    audio_bytes: bytes,
    sample_rate: int = 16000,
    sample_width: int = 2,
    channels: int = 1
) -> float:
    """Calculate audio duration in seconds.
    
    Args:
        audio_bytes: Audio data
        sample_rate: Sample rate in Hz
        sample_width: Bytes per sample
        channels: Number of channels
        
    Returns:
        Duration in seconds
    """
    num_samples = len(audio_bytes) / (sample_width * channels)
    return num_samples / sample_rate
