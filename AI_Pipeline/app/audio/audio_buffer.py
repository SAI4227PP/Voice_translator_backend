"""
Audio buffer management for streaming audio processing.
"""
import asyncio
from collections import deque
from typing import Optional, Callable
import numpy as np
from app.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


class AudioBuffer:
    """Buffer for accumulating audio chunks."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 4096,
        max_buffer_size: int = 32768
    ):
        """Initialize audio buffer.
        
        Args:
            sample_rate: Audio sample rate in Hz
            chunk_size: Size of audio chunks in bytes
            max_buffer_size: Maximum buffer size in bytes
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.max_buffer_size = max_buffer_size
        
        self.buffer = bytearray()
        self.chunks_queue = deque()
        
        logger.debug(
            "audio_buffer_initialized",
            sample_rate=sample_rate,
            chunk_size=chunk_size
        )
    
    def add(self, data: bytes) -> None:
        """Add audio data to buffer.
        
        Args:
            data: Raw audio bytes
        """
        self.buffer.extend(data)
        
        # Prevent buffer overflow
        if len(self.buffer) > self.max_buffer_size:
            excess = len(self.buffer) - self.max_buffer_size
            self.buffer = self.buffer[excess:]
            logger.warning(
                "buffer_overflow_trimmed",
                excess_bytes=excess
            )
    
    def get_chunk(self) -> Optional[bytes]:
        """Get a chunk of audio data.
        
        Returns:
            Audio chunk or None if insufficient data
        """
        if len(self.buffer) >= self.chunk_size:
            chunk = bytes(self.buffer[:self.chunk_size])
            self.buffer = self.buffer[self.chunk_size:]
            return chunk
        return None
    
    def get_all(self) -> bytes:
        """Get all buffered audio data.
        
        Returns:
            All buffered audio bytes
        """
        data = bytes(self.buffer)
        self.buffer.clear()
        return data
    
    def clear(self) -> None:
        """Clear the buffer."""
        self.buffer.clear()
        self.chunks_queue.clear()
    
    def size(self) -> int:
        """Get current buffer size in bytes.
        
        Returns:
            Buffer size
        """
        return len(self.buffer)
    
    def duration_ms(self) -> float:
        """Get duration of buffered audio in milliseconds.
        
        Returns:
            Duration in milliseconds
        """
        # Assuming PCM16 (2 bytes per sample, mono)
        samples = len(self.buffer) / 2
        duration_seconds = samples / self.sample_rate
        return duration_seconds * 1000


class StreamingAudioBuffer:
    """Streaming audio buffer with callback support."""
    
    def __init__(
        self,
        callback: Callable[[bytes], None],
        sample_rate: int = 16000,
        chunk_duration_ms: int = 100
    ):
        """Initialize streaming buffer.
        
        Args:
            callback: Function to call when chunk is ready
            sample_rate: Audio sample rate
            chunk_duration_ms: Target chunk duration in milliseconds
        """
        self.callback = callback
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        
        # Calculate chunk size in bytes (PCM16, mono)
        samples_per_chunk = int(sample_rate * chunk_duration_ms / 1000)
        self.chunk_size = samples_per_chunk * 2  # 2 bytes per sample
        
        self.buffer = AudioBuffer(sample_rate, self.chunk_size)
        self._processing = False
        
        logger.debug(
            "streaming_buffer_initialized",
            chunk_size=self.chunk_size,
            chunk_duration_ms=chunk_duration_ms
        )
    
    async def add(self, data: bytes) -> None:
        """Add audio data and process if ready.
        
        Args:
            data: Raw audio bytes
        """
        self.buffer.add(data)
        
        # Process chunks if not already processing
        if not self._processing:
            await self._process_chunks()
    
    async def _process_chunks(self) -> None:
        """Process available chunks."""
        self._processing = True
        
        try:
            while True:
                chunk = self.buffer.get_chunk()
                if chunk is None:
                    break
                
                # Call callback
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(chunk)
                else:
                    self.callback(chunk)
        
        finally:
            self._processing = False
    
    async def flush(self) -> None:
        """Flush remaining buffered data."""
        remaining = self.buffer.get_all()
        if remaining and len(remaining) > 0:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(remaining)
            else:
                self.callback(remaining)
    
    def clear(self) -> None:
        """Clear the buffer."""
        self.buffer.clear()
