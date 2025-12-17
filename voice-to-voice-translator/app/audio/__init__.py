"""Audio module initialization."""
from app.audio.audio_buffer import AudioBuffer, StreamingAudioBuffer
from app.audio.audio_utils import (
    bytes_to_numpy,
    numpy_to_bytes,
    normalize_audio,
    denormalize_audio,
    resample_audio,
    convert_to_mono,
    apply_gain,
    compute_rms,
    detect_silence,
    trim_silence,
    chunk_audio,
    calculate_duration
)
from app.audio.pcm_validator import PCMValidator, validate_audio_chunk

__all__ = [
    "AudioBuffer",
    "StreamingAudioBuffer",
    "bytes_to_numpy",
    "numpy_to_bytes",
    "normalize_audio",
    "denormalize_audio",
    "resample_audio",
    "convert_to_mono",
    "apply_gain",
    "compute_rms",
    "detect_silence",
    "trim_silence",
    "chunk_audio",
    "calculate_duration",
    "PCMValidator",
    "validate_audio_chunk",
]
