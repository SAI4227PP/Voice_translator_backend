"""
Pipeline manager for orchestrating STT -> Translation -> TTS flow.
"""
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from app.config import get_logger, get_settings
from app.pipeline.stt import STTFactory
from app.pipeline.translation_runtime import get_translator
from app.pipeline.tts_runtime import TTSFactory
from app.audio.audio_buffer import AudioBuffer
from app.utils.exceptions import PipelineError

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class PipelineResult:
    """Result from pipeline processing."""
    recognized_text: str
    translated_text: str
    audio_data: bytes
    source_language: str
    target_language: str
    processing_time_ms: float


class PipelineManager:
    """Orchestrates the complete voice translation pipeline."""
    
    def __init__(self):
        """Initialize pipeline manager."""
        self.translator = get_translator()
        self._stt_engines: Dict[str, Any] = {}
        self._tts_engines: Dict[str, Any] = {}
        self._recognizers: Dict[str, Any] = {}
        self._chunk_text_buffers: Dict[str, str] = {}
        
        logger.info("pipeline_manager_initialized")
    
    def _get_stt_engine(self, language: str):
        """Get or create STT engine for language.
        
        Args:
            language: Language code
            
        Returns:
            STT engine
        """
        if language not in self._stt_engines:
            self._stt_engines[language] = STTFactory.get_engine(language)
        return self._stt_engines[language]
    
    def _get_tts_engine(self, language: str):
        """Get or create TTS engine for language.
        
        Args:
            language: Language code
            
        Returns:
            TTS engine
        """
        if language not in self._tts_engines:
            self._tts_engines[language] = TTSFactory.get_engine(language)
        return self._tts_engines[language]
    
    def _get_recognizer(self, user_id: str, language: str):
        """Get or create recognizer for user.
        
        Args:
            user_id: User ID
            language: Language code
            
        Returns:
            Recognizer instance
        """
        key = f"{user_id}_{language}"
        if key not in self._recognizers:
            engine = self._get_stt_engine(language)
            self._recognizers[key] = engine.create_recognizer()
        return self._recognizers[key]
    
    async def process_audio_chunk(
        self,
        audio_data: bytes,
        user_id: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[str]:
        """Process streaming audio chunk (partial results).
        
        Args:
            audio_data: Raw audio bytes (PCM16)
            user_id: User ID for recognizer tracking
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Partial recognized text or None
        """
        try:
            # Get STT engine and recognizer
            stt_engine = self._get_stt_engine(source_lang)
            recognizer = self._get_recognizer(user_id, source_lang)
            
            # Recognize audio
            result = await stt_engine.recognize_async(audio_data, recognizer)
            
            # Return partial result if available
            partial_text = result.get("partial", "")
            if partial_text:
                logger.debug(
                    "partial_recognition",
                    user_id=user_id,
                    text=partial_text
                )
            
            return partial_text
        
        except Exception as e:
            logger.error(
                "audio_chunk_processing_failed",
                error=str(e),
                user_id=user_id,
                exc_info=True
            )
            return None
    
    async def process_complete_audio(
        self,
        audio_data: bytes,
        user_id: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[PipelineResult]:
        """Process complete audio through full pipeline.
        
        Args:
            audio_data: Complete audio bytes
            user_id: User ID
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Pipeline result or None if processing failed
        """
        import time
        start_time = time.time()
        
        try:
            # Step 1: Speech Recognition
            stt_engine = self._get_stt_engine(source_lang)
            recognizer = self._get_recognizer(user_id, source_lang)
            
            # Finalize recognition
            stt_result = stt_engine.finalize(recognizer)
            recognized_text = stt_result.get("text", "")
            
            if not recognized_text or not recognized_text.strip():
                logger.warning(
                    "no_text_recognized",
                    user_id=user_id,
                    source_lang=source_lang
                )
                return None
            
            logger.info(
                "stt_complete",
                user_id=user_id,
                text=recognized_text
            )
            
            # Step 2: Translation
            translated_text = await self.translator.translate(
                recognized_text,
                source_lang,
                target_lang
            )
            
            logger.info(
                "translation_complete",
                user_id=user_id,
                original=recognized_text,
                translated=translated_text
            )
            
            # Step 3: Text-to-Speech
            tts_engine = self._get_tts_engine(target_lang)
            audio_bytes = await tts_engine.synthesize_to_bytes_async(translated_text)
            
            logger.info(
                "tts_complete",
                user_id=user_id,
                audio_size=len(audio_bytes)
            )
            
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000
            
            return PipelineResult(
                recognized_text=recognized_text,
                translated_text=translated_text,
                audio_data=audio_bytes,
                source_language=source_lang,
                target_language=target_lang,
                processing_time_ms=processing_time
            )
        
        except Exception as e:
            logger.error(
                "pipeline_processing_failed",
                error=str(e),
                user_id=user_id,
                exc_info=True
            )
            raise PipelineError(f"Pipeline processing failed: {e}")
    
    async def translate_text_to_speech(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        mode: str = "full_sentence",
        stream_id: Optional[str] = None
    ) -> Optional[bytes]:
        """Translate text and synthesize to speech.
        
        Args:
            text: Text to translate
            source_lang: Source language
            target_lang: Target language
            mode: "chunk" for streaming fragments, "full_sentence" for complete text
            stream_id: Optional stream key for chunk buffering

        Returns:
            Audio bytes or None
        """
        try:
            normalized_mode = (mode or "full_sentence").strip().lower()
            if normalized_mode not in {"chunk", "full_sentence"}:
                normalized_mode = "full_sentence"

            raw_text = (text or "").strip()
            if not raw_text:
                return None

            effective_text = raw_text
            if normalized_mode == "chunk" and stream_id:
                # Keep small rolling context so chunk-by-chunk translation has continuity.
                prev = self._chunk_text_buffers.get(stream_id, "")
                merged = f"{prev} {raw_text}".strip() if prev else raw_text
                # Bound memory and latency: keep only recent context.
                self._chunk_text_buffers[stream_id] = merged[-600:]
                effective_text = self._chunk_text_buffers[stream_id]
            elif normalized_mode == "full_sentence" and stream_id:
                # Final sentence closes the chunk stream context.
                self._chunk_text_buffers.pop(stream_id, None)

            # Translate
            translated = await self.translator.translate(
                effective_text,
                source_lang,
                target_lang
            )
            
            # Synthesize
            tts_engine = self._get_tts_engine(target_lang)
            audio_bytes = await tts_engine.synthesize_to_bytes_async(translated)
            
            return audio_bytes
        
        except Exception as e:
            logger.error(
                "text_to_speech_translation_failed",
                error=str(e),
                exc_info=True
            )
            return None

    async def translate_chunk_to_speech(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        stream_id: str
    ) -> Optional[bytes]:
        """Translate and synthesize a chunk while preserving short per-stream context."""
        return await self.translate_text_to_speech(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            mode="chunk",
            stream_id=stream_id,
        )
    
    def reset_recognizer(self, user_id: str, language: str) -> None:
        """Reset recognizer for user.
        
        Args:
            user_id: User ID
            language: Language code
        """
        key = f"{user_id}_{language}"
        if key in self._recognizers:
            del self._recognizers[key]
            logger.debug("recognizer_reset", user_id=user_id, language=language)
    
    def cleanup_user(self, user_id: str) -> None:
        """Clean up resources for user.
        
        Args:
            user_id: User ID
        """
        # Remove all recognizers for this user
        to_remove = [key for key in self._recognizers if key.startswith(f"{user_id}_")]
        for key in to_remove:
            del self._recognizers[key]

        # Drop any chunk-text buffers associated with this user.
        stream_prefix = f"{user_id}:"
        stale_streams = [k for k in self._chunk_text_buffers if k.startswith(stream_prefix)]
        for key in stale_streams:
            del self._chunk_text_buffers[key]

        logger.info("pipeline_user_cleanup", user_id=user_id, removed=len(to_remove), chunk_streams_removed=len(stale_streams))

    def preload_engines(
        self,
        stt_languages: Optional[list[str]] = None,
        tts_languages: Optional[list[str]] = None
    ) -> None:
        """Preload STT and TTS engines for specified languages (warm start).
        
        This ensures models are loaded before any requests arrive,
        eliminating cold start delays.
        
        Args:
            stt_languages: List of language codes for STT preloading
            tts_languages: List of language codes for TTS preloading
        """
        if stt_languages:
            logger.info("pipeline_preloading_stt_engines", languages=stt_languages)
            for language in stt_languages:
                try:
                    self._get_stt_engine(language)
                    logger.info("pipeline_stt_engine_preloaded", language=language)
                except Exception as e:
                    logger.error(
                        "pipeline_stt_engine_preload_failed",
                        language=language,
                        error=str(e),
                        exc_info=True
                    )
        
        if tts_languages:
            logger.info("pipeline_preloading_tts_engines", languages=tts_languages)
            for language in tts_languages:
                try:
                    self._get_tts_engine(language)
                    logger.info("pipeline_tts_engine_preloaded", language=language)
                except Exception as e:
                    logger.error(
                        "pipeline_tts_engine_preload_failed",
                        language=language,
                        error=str(e),
                        exc_info=True
                    )
        
        logger.info("pipeline_engine_preload_complete")

# Global pipeline manager instance
_pipeline_manager: Optional[PipelineManager] = None


def get_pipeline_manager() -> PipelineManager:
    """Get global pipeline manager instance.
    
    Returns:
        PipelineManager instance
    """
    global _pipeline_manager
    if _pipeline_manager is None:
        _pipeline_manager = PipelineManager()
    return _pipeline_manager

