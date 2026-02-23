"""
Main application entry point.
"""
import os
import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, HTTPException, status, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import List, Optional

# Configure environment variables before any imports that might use numba
os.environ['NUMBA_CACHE_DIR'] = '/tmp/numba_cache'
os.environ.setdefault('NUMBA_DISABLE_JIT', '0')
# Configure matplotlib and fontconfig to use writable directories
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'
os.environ['FONTCONFIG_PATH'] = '/tmp/fontconfig'
# Configure SpaCy cache directories (MUST be writable)
os.environ['HOME'] = '/tmp'
# ARGOS_PACKAGES_DIR should be set via Dockerfile or .env
# Default only if not set: /app/models/translate/argos-packages
if 'ARGOS_PACKAGES_DIR' not in os.environ:
    os.environ['ARGOS_PACKAGES_DIR'] = '/app/models/translate/argos-packages'


from app.config import setup_logging, get_settings, logger
from app.server import get_websocket_server

settings = get_settings()


async def initialize_spacy_model():
    """Initialize and warm start spaCy model.
    
    This loads the xx_sent_ud_sm model once at startup and caches it globally,
    preventing repeated downloads or loads during runtime.
    """
    logger.info("spacy_warm_start_initializing")
    
    try:
        import spacy
        # Load model (will be cached globally)
        nlp = spacy.load("xx_sent_ud_sm")
        
        # Perform a test processing to fully warm up the model
        test_doc = nlp("Test sentence for warm start.")
        
        logger.info(
            "spacy_warm_start_complete",
            model="xx_sent_ud_sm",
            pipeline_components=nlp.pipe_names
        )
        
    except (OSError, ImportError) as e:
        logger.error(
            "spacy_warm_start_failed",
            error=str(e),
            message="spaCy model 'xx_sent_ud_sm' is missing or failed to load",
            exc_info=True
        )
        raise RuntimeError(
            "spaCy model 'xx_sent_ud_sm' is missing from the image.\n"
            "Please rebuild your Docker image to include the model.\n"
            "See Dockerfile for installation instructions.\n"
            f"Original error: {e}"
        )


async def initialize_stt_models():
    """Initialize and warm up STT models for configured languages.
    
    This implements warm start by preloading STT models at application startup
    instead of lazy loading them on first use (cold start).
    """
    if not settings.stt_enable_warm_start:
        logger.info("stt_warm_start_disabled")
        return
    
    languages_to_preload = settings.stt_preload_languages_list
    
    if not languages_to_preload:
        logger.warning("stt_warm_start_no_languages_configured")
        return
    
    logger.info(
        "stt_warm_start_initializing",
        languages=languages_to_preload,
        count=len(languages_to_preload)
    )
    
    from app.pipeline.stt import STTFactory
    import time
    
    start_time = time.time()
    successfully_loaded = []
    failed_to_load = []
    
    for language in languages_to_preload:
        try:
            logger.info(f"stt_preloading_model", language=language)
            
            # Create and cache the STT engine - this loads the model
            # STTFactory.create() gets model_path from settings internally
            engine = STTFactory.create(
                engine_type=settings.stt_engine,
                language=language
            )
            
            # Create a test recognizer to fully warm up the model
            recognizer = engine.create_recognizer()
            
            successfully_loaded.append(language)
            logger.info(f"stt_model_preloaded_successfully", language=language)
            
        except Exception as e:
            failed_to_load.append(language)
            logger.error(
                "stt_model_preload_failed",
                language=language,
                error=str(e),
                exc_info=True
            )
    
    total_time = time.time() - start_time
    
    logger.info(
        "stt_warm_start_complete",
        total_time_seconds=round(total_time, 2),
        successfully_loaded=successfully_loaded,
        failed_to_load=failed_to_load,
        success_count=len(successfully_loaded),
        failure_count=len(failed_to_load)
    )


async def initialize_translation_models():
    """Initialize and warm up Translation models.
    
    This implements warm start by preloading translation models at application startup.
    Can warm up all installed packages or just common pairs based on configuration.
    """
    if not settings.translation_enable_warm_start:
        logger.info("translation_warm_start_disabled")
        return
    
    logger.info(
        "translation_warm_start_initializing",
        mode=settings.translation_warm_start_mode
    )
    
    from app.pipeline.translate import get_translator
    import time
    
    start_time = time.time()
    
    try:
        translator = get_translator()
        
        if settings.translation_warm_start_mode == "all":
            # Warm up all installed translation packages
            translator.warm_up()
        else:
            # Warm up only common language pairs
            common_pairs = settings.translation_common_pairs_list
            if common_pairs:
                translator.warm_up_common_pairs(common_pairs)
            else:
                logger.warning("translation_warm_start_no_pairs_configured")
        
        total_time = time.time() - start_time
        
        logger.info(
            "translation_warm_start_complete",
            total_time_seconds=round(total_time, 2),
            mode=settings.translation_warm_start_mode
        )
        
    except Exception as e:
        logger.error(
            "translation_warm_start_failed",
            error=str(e),
            exc_info=True
        )


async def initialize_tts_models():
    """Initialize and warm up TTS models for configured languages.
    
    This implements warm start by preloading TTS models at application startup
    instead of lazy loading them on first use (cold start).
    """
    if not settings.tts_enable_warm_start:
        logger.info("tts_warm_start_disabled")
        return
    
    languages_to_preload = settings.tts_preload_languages_list
    
    if not languages_to_preload:
        logger.warning("tts_warm_start_no_languages_configured")
        return
    
    logger.info(
        "tts_warm_start_initializing",
        languages=languages_to_preload,
        count=len(languages_to_preload)
    )
    
    from app.pipeline.tts import TTSFactory
    import time
    
    start_time = time.time()
    successfully_loaded = []
    failed_to_load = []
    
    for language in languages_to_preload:
        try:
            logger.info(f"tts_preloading_model", language=language)
            
            # Create and cache the TTS engine - this loads the model
            engine = TTSFactory.create(engine_type=settings.tts_engine, language=language)
            
            # Perform a test synthesis to fully warm up the model
            test_text = "Hello" if language == "en" else "Test"
            await engine.synthesize_to_bytes_async(test_text)
            
            successfully_loaded.append(language)
            logger.info(f"tts_model_preloaded_successfully", language=language)
            
        except Exception as e:
            failed_to_load.append(language)
            logger.error(
                "tts_model_preload_failed",
                language=language,
                error=str(e),
                exc_info=True
            )
    
    # Also warm up worker pool engines
    try:
        from app.workers import get_tts_pool
        tts_pool = get_tts_pool()
        await tts_pool.preload_engines(successfully_loaded)
    except Exception as e:
        logger.warning(
            "tts_worker_pool_preload_failed",
            error=str(e),
            exc_info=True
        )
    
    total_time = time.time() - start_time
    
    logger.info(
        "tts_warm_start_complete",
        total_time_seconds=round(total_time, 2),
        successfully_loaded=successfully_loaded,
        failed_to_load=failed_to_load,
        success_count=len(successfully_loaded),
        failure_count=len(failed_to_load)
    )


# Pydantic models for request validation
class TranslateRequest(BaseModel):
    """Request model for text translation."""
    text: str = Field(..., description="Text to translate")
    source_language: str = Field(..., description="Source language code (e.g., 'en')")
    target_language: str = Field(..., description="Target language code (e.g., 'es')")


class BatchTranslateRequest(BaseModel):
    """Request model for batch text translation."""
    texts: List[str] = Field(..., description="List of texts to translate", max_items=100)
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")


class TTSRequest(BaseModel):
    """Request model for TTS audio generation."""
    text: str = Field(..., description="Text to synthesize")
    language: str = Field(..., description="Language code (e.g., 'en', 'hi', 'es')")
    format: str = Field(default="wav", description="Audio format: 'wav' or 'mp3'")


class STTRequest(BaseModel):
    """Request model for STT audio transcription."""
    audio_data: str = Field(..., description="Base64-encoded audio data (PCM16 or WAV)")
    language: str = Field(..., description="Language code (e.g., 'en', 'hi', 'te')")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    return_confidence: bool = Field(default=False, description="Include confidence score in response")


class BatchSTTRequest(BaseModel):
    """Request model for batch STT transcription."""
    audio_files: List[str] = Field(..., description="List of base64-encoded audio data", max_items=50)
    language: str = Field(..., description="Language code for all audio files")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    return_confidence: bool = Field(default=False, description="Include confidence scores")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(
        "application_starting",
        environment=settings.environment,
        host=settings.host,
        port=settings.port
    )
    
    # Initialize all models for warm start (prevents cold start delays)
    # Run initializations in sequence to avoid resource contention
    
    # 1. Initialize spaCy model (used by Argos translation)
    try:
        await initialize_spacy_model()
    except Exception as e:
        logger.error(
            "spacy_initialization_failed",
            error=str(e),
            exc_info=True
        )
        # Don't exit - app can continue without spaCy
    
    # 2. Initialize STT models
    try:
        await initialize_stt_models()
    except Exception as e:
        logger.error(
            "stt_initialization_failed",
            error=str(e),
            exc_info=True
        )
    
    # 3. Initialize Translation models
    try:
        await initialize_translation_models()
    except Exception as e:
        logger.error(
            "translation_initialization_failed",
            error=str(e),
            exc_info=True
        )
    
    # 4. Initialize TTS models
    try:
        await initialize_tts_models()
    except Exception as e:
        logger.error(
            "tts_initialization_failed",
            error=str(e),
            exc_info=True
        )
    
    # 5. Preload pipeline manager engines
    try:
        from app.pipeline import get_pipeline_manager
        pipeline_manager = get_pipeline_manager()
        
        stt_langs = settings.stt_preload_languages_list if settings.stt_enable_warm_start else []
        tts_langs = settings.tts_preload_languages_list if settings.tts_enable_warm_start else []
        
        if stt_langs or tts_langs:
            pipeline_manager.preload_engines(
                stt_languages=stt_langs,
                tts_languages=tts_langs
            )
            logger.info("pipeline_manager_preload_complete")
    except Exception as e:
        logger.error(
            "pipeline_manager_preload_failed",
            error=str(e),
            exc_info=True
        )
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    # Cleanup TTS cache if needed
    try:
        from app.pipeline.tts import TTSFactory
        TTSFactory.clear_cache()
    except Exception as e:
        logger.warning("tts_cleanup_failed", error=str(e))


# Create FastAPI application
app = FastAPI(
    title="Voice-to-Voice Translator",
    description="Real-time voice translation system",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Voice-to-Voice Translator",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from app.server import get_connection_manager
    from app.rooms import get_room_manager
    
    conn_mgr = get_connection_manager()
    room_mgr = get_room_manager()
    
    return {
        "status": "healthy",
        "connections": conn_mgr.get_connection_count(),
        "rooms": room_mgr.get_room_count(),
        "total_users": room_mgr.get_total_users()
    }


@app.get("/stats")
async def get_server_statistics():
    """Get detailed server statistics and metrics."""
    from app.server import get_connection_manager
    from app.rooms import get_room_manager
    
    conn_mgr = get_connection_manager()
    room_mgr = get_room_manager()
    
    # Get worker pool statistics - avoid importing if it causes errors
    translation_stats = {"total": settings.translation_workers, "busy": 0, "queue_size": 0}
    tts_stats = {"total": settings.tts_workers, "busy": 0, "queue_size": 0}
    
    try:
        from app.workers import get_translation_pool, get_tts_pool
        
        translation_pool = get_translation_pool()
        tts_pool = get_tts_pool()
        
        if hasattr(translation_pool, 'get_busy_count'):
            translation_stats["busy"] = translation_pool.get_busy_count()
        if hasattr(translation_pool, 'get_queue_size'):
            translation_stats["queue_size"] = translation_pool.get_queue_size()
            
        if hasattr(tts_pool, 'get_busy_count'):
            tts_stats["busy"] = tts_pool.get_busy_count()
        if hasattr(tts_pool, 'get_queue_size'):
            tts_stats["queue_size"] = tts_pool.get_queue_size()
    except Exception as e:
        logger.warning("worker_stats_unavailable", error=str(e))
    
    return {
        "server": {
            "version": "1.0.0",
            "environment": settings.environment
        },
        "connections": {
            "total": conn_mgr.get_connection_count(),
            "active": conn_mgr.get_connection_count()
        },
        "rooms": {
            "total": room_mgr.get_room_count(),
            "active": room_mgr.get_room_count()
        },
        "workers": {
            "translation": translation_stats,
            "tts": tts_stats
        }
    }


@app.get("/config")
async def get_system_configuration():
    """Get current system configuration."""
    from app.utils.model_scanner import ModelScanner
    
    # Get dynamic language information from model scanner
    scanner = ModelScanner()
    stt_languages = scanner.get_available_stt_languages()
    translation_languages = scanner.get_available_translation_languages()
    tts_languages = scanner.get_available_tts_languages()
    
    # Convert to simple dict for supported_languages field
    supported_langs = {}
    
    # Add STT languages
    for code, info in stt_languages.items():
        supported_langs[code] = info.get("name", code.upper())
    
    # Add translation languages (merge with STT)
    for code, info in translation_languages.items():
        if code not in supported_langs:
            supported_langs[code] = info.get("name", code.upper())
    
    # Add TTS languages (merge with previous)
    for code, info in tts_languages.items():
        if code not in supported_langs and code != "multilingual":
            supported_langs[code] = info.get("name", code.upper())
    
    return {
        "audio": {
            "sample_rate": settings.audio_sample_rate,
            "channels": settings.audio_channels,
            "chunk_size": settings.audio_chunk_size,
            "format": settings.audio_format
        },
        "limits": {
            "max_connections": settings.max_connections,
            "max_connections_per_ip": settings.max_connections_per_ip,
            "max_users_per_room": settings.max_users_per_room,
            "max_message_size": settings.max_message_size,
            "idle_timeout": settings.idle_timeout,
            "room_timeout": settings.room_timeout
        },
        "rate_limits": {
            "messages_per_second": settings.max_messages_per_second,
            "requests_per_minute": settings.max_requests_per_minute,
            "rate_limit_per_minute": settings.rate_limit_per_minute
        },
        "workers": {
            "translation_workers": settings.translation_workers,
            "tts_workers": settings.tts_workers,
            "worker_threads": settings.worker_threads,
            "queue_size": settings.queue_size
        },
        "models": {
            "stt_engine": settings.stt_engine,
            "translation_engine": settings.translation_engine,
            "tts_engine": settings.tts_engine,
            "vosk_model_base_path": settings.vosk_model_base_path,
            "argos_model_path": settings.argos_model_path,
            "coqui_model_path": settings.coqui_model_path,
            "available_models": {
                "stt": stt_languages,
                "translation": translation_languages,
                "tts": tts_languages
            },
            "supported_languages": supported_langs
        },
        "features": {
            "authentication_enabled": settings.enable_auth,
            "rate_limiting_enabled": True,
            "metrics_enabled": settings.enable_metrics,
            "gpu_enabled": settings.enable_gpu
        },
        "websocket": {
            "ping_interval": settings.ws_ping_interval,
            "ping_timeout": settings.ws_ping_timeout
        },
        "environment": {
            "env": settings.environment,
            "debug": settings.debug,
            "host": settings.host,
            "port": settings.port,
            "cors_origins": settings.cors_origins
        }
    }


@app.get("/languages/supported")
async def get_supported_languages():
    """Get list of supported languages for STT, Translation, and TTS based on downloaded models."""
    from app.utils.model_scanner import ModelScanner
    
    scanner = ModelScanner()
    
    return {
        "stt": scanner.get_available_stt_languages(),
        "translation": scanner.get_available_translation_languages(),
        "tts": scanner.get_available_tts_languages()
    }


@app.get("/languages/pairs")
async def get_translation_pairs():
    """Get available translation language pairs based on installed packages."""
    from app.utils.model_scanner import ModelScanner
    
    scanner = ModelScanner()
    pairs = scanner.get_translation_pairs()
    
    return {
        "pairs": pairs,
        "count": len(pairs)
    }


@app.post("/translate")
async def translate_text(request: TranslateRequest):
    """Translate text without audio processing.
    
    Request body:
        {
            "text": "Hello, how are you?",
            "source_language": "en",
            "target_language": "es"
        }
    """
    from app.pipeline.translate import get_translator
    from app.utils.model_scanner import ModelScanner
    import time
    
    try:
        # Get available languages dynamically
        scanner = ModelScanner()
        available_languages = scanner.get_available_translation_languages()
        
        # Check if source language is in supported languages
        if request.source_language not in available_languages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": f"Source language '{request.source_language}' is not supported",
                    "available_languages": list(available_languages.keys()),
                    "message": "Check /languages/supported for available languages"
                }
            )
        
        # Check if target language is in supported languages
        if request.target_language not in available_languages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": f"Target language '{request.target_language}' is not supported",
                    "available_languages": list(available_languages.keys()),
                    "message": "Check /languages/supported for available languages"
                }
            )
        
        # Don't check for specific pair availability - let translator auto-install
        # The translator will handle package installation if needed
        
        # Get translator and translate (with auto-install)
        translator = get_translator()
        
        start_time = time.time()
        translated_text = await translator.translate(
            request.text, 
            request.source_language, 
            request.target_language
        )
        processing_time = (time.time() - start_time) * 1000
        
        return {
            "original_text": request.text,
            "translated_text": translated_text,
            "source_language": request.source_language,
            "target_language": request.target_language,
            "processing_time_ms": round(processing_time, 2)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("translation_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}"
        )


@app.post("/translate/batch")
async def translate_batch(request: BatchTranslateRequest):
    """Translate multiple texts in one request.
    
    Request body:
        {
            "texts": ["Hello", "How are you?", "Goodbye"],
            "source_language": "en",
            "target_language": "es"
        }
    """
    from app.pipeline.translate import get_translator
    from app.utils.model_scanner import ModelScanner
    import time
    
    try:
        # Get available languages dynamically
        scanner = ModelScanner()
        available_languages = scanner.get_available_translation_languages()
        translation_pairs = scanner.get_translation_pairs()
        
        # Check if source language is available
        if request.source_language not in available_languages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": f"Source language '{request.source_language}' is not available",
                    "available_languages": list(available_languages.keys()),
                    "message": "Check /languages/supported for available languages"
                }
            )
        
        # Check if target language is in supported languages
        if request.target_language not in available_languages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": f"Target language '{request.target_language}' is not supported",
                    "available_languages": list(available_languages.keys()),
                    "message": "Check /languages/supported for available languages"
                }
            )
        
        # Don't check for specific pair availability - let translator auto-install
        # The translator will handle package installation if needed
        
        # Get translator (with auto-install support)
        translator = get_translator()
        
        # Translate all texts
        start_time = time.time()
        translations = []
        
        for text in request.texts:
            translated_text = await translator.translate(
                text, 
                request.source_language, 
                request.target_language
            )
            translations.append({
                "original": text,
                "translated": translated_text
            })
        
        processing_time = (time.time() - start_time) * 1000
        
        return {
            "translations": translations,
            "source_language": request.source_language,
            "target_language": request.target_language,
            "total": len(translations),
            "processing_time_ms": round(processing_time, 2)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("batch_translation_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch translation failed: {str(e)}"
        )


@app.post("/tts/generate")
async def generate_tts_audio(request: TTSRequest):
    """Generate TTS audio for the provided text.
    
    Request body:
        {
            "text": "Hello, this is a test message",
            "language": "en",
            "format": "wav"
        }
    
    Returns:
        Binary audio data (WAV or MP3 format)
    """
    from fastapi.responses import Response
    from app.pipeline.tts import get_tts_factory
    from app.utils.model_scanner import ModelScanner
    import time
    import io
    
    try:
        # Validate format
        if request.format not in ["wav", "mp3"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid format '{request.format}'. Supported formats: 'wav', 'mp3'"
            )
        
        # Get available TTS languages
        scanner = ModelScanner()
        available_tts_languages = scanner.get_available_tts_languages()
        
        # Check if language is supported
        if request.language not in available_tts_languages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": f"Language '{request.language}' is not supported for TTS",
                    "available_languages": list(available_tts_languages.keys()),
                    "message": "Check /languages/supported for available TTS languages"
                }
            )
        
        # Get TTS engine
        tts_factory = get_tts_factory()
        tts_engine = tts_factory.get_engine(request.language)
        
        # Generate audio
        start_time = time.time()
        audio_data = await tts_engine.synthesize_async(request.text)
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(
            "tts_generated",
            language=request.language,
            text_length=len(request.text),
            audio_size=len(audio_data),
            processing_time_ms=round(processing_time, 2)
        )
        
        # Return audio as response
        if request.format == "wav":
            media_type = "audio/wav"
        else:
            media_type = "audio/mpeg"
        
        return Response(
            content=audio_data,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="tts_output.{request.format}"',
                "X-Processing-Time-Ms": str(round(processing_time, 2))
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("tts_generation_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS generation failed: {str(e)}"
        )


@app.post("/stt/transcribe")
async def transcribe_audio(request: STTRequest):
    """Transcribe audio to text using STT engine.
    
    Request body:
        {
            "audio_data": "<base64-encoded audio>",
            "language": "en",
            "sample_rate": 16000,
            "return_confidence": false
        }
    
    Returns:
        {
            "text": "transcribed text",
            "language": "en",
            "confidence": 0.95,  // if return_confidence=true
            "processing_time_ms": 123.45
        }
    """
    from app.pipeline.stt import STTFactory
    from app.utils.model_scanner import ModelScanner
    import time
    import base64
    
    try:
        # Get available STT languages
        scanner = ModelScanner()
        available_stt_languages = scanner.get_available_stt_languages()
        
        # Check if language is supported
        if request.language not in available_stt_languages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": f"Language '{request.language}' is not supported for STT",
                    "available_languages": list(available_stt_languages.keys()),
                    "message": "Check /languages/supported for available STT languages"
                }
            )
        
        # Decode base64 audio data
        try:
            audio_bytes = base64.b64decode(request.audio_data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 audio data: {str(e)}"
            )
        
        # Get STT engine
        stt_engine = STTFactory.get_engine(request.language)
        
        # Create recognizer
        recognizer = stt_engine.create_recognizer()
        
        # Transcribe audio
        start_time = time.time()
        result = await stt_engine.recognize_async(audio_bytes, recognizer)
        
        # Finalize to get complete result
        final_result = stt_engine.finalize(recognizer)
        processing_time = (time.time() - start_time) * 1000
        
        # Extract text and confidence
        transcribed_text = final_result.get("text", "")
        
        logger.info(
            "stt_transcribed",
            language=request.language,
            text_length=len(transcribed_text),
            audio_size=len(audio_bytes),
            processing_time_ms=round(processing_time, 2)
        )
        
        # Build response
        response = {
            "text": transcribed_text,
            "language": request.language,
            "processing_time_ms": round(processing_time, 2)
        }
        
        # Add confidence if requested (Vosk doesn't provide overall confidence)
        if request.return_confidence:
            response["confidence"] = final_result.get("confidence", None)
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("stt_transcription_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"STT transcription failed: {str(e)}"
        )


@app.post("/stt/transcribe-file")
async def transcribe_audio_file(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: str = Form(default="en", description="Language code"),
    return_confidence: bool = Form(default=False, description="Include confidence score")
):
    """Transcribe audio file to text using STT engine.
    
    Upload an audio file (WAV, MP3, etc.) for transcription.
    
    Form Parameters:
        file: Audio file (multipart/form-data)
        language: Language code (default: "en")
        return_confidence: Include confidence score (default: false)
    
    Returns:
        {
            "text": "transcribed text",
            "language": "en",
            "confidence": 0.95,  // if return_confidence=true
            "file_size": 12345,
            "processing_time_ms": 123.45
        }
    """
    from fastapi import File, Form, UploadFile
    from app.pipeline.stt import STTFactory
    from app.utils.model_scanner import ModelScanner
    import time
    
    try:
        # Get available STT languages
        scanner = ModelScanner()
        available_stt_languages = scanner.get_available_stt_languages()
        
        # Check if language is supported
        if language not in available_stt_languages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": f"Language '{language}' is not supported for STT",
                    "available_languages": list(available_stt_languages.keys()),
                    "message": "Check /languages/supported for available STT languages"
                }
            )
        
        # Read audio file
        audio_bytes = await file.read()
        file_size = len(audio_bytes)
        
        # Check file size (limit to 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {max_size} bytes"
            )
        
        # Get STT engine
        stt_engine = STTFactory.get_engine(language)
        
        # Create recognizer
        recognizer = stt_engine.create_recognizer()
        
        # Transcribe audio
        start_time = time.time()
        result = await stt_engine.recognize_async(audio_bytes, recognizer)
        
        # Finalize to get complete result
        final_result = stt_engine.finalize(recognizer)
        processing_time = (time.time() - start_time) * 1000
        
        # Extract text
        transcribed_text = final_result.get("text", "")
        
        logger.info(
            "stt_file_transcribed",
            language=language,
            filename=file.filename,
            file_size=file_size,
            text_length=len(transcribed_text),
            processing_time_ms=round(processing_time, 2)
        )
        
        # Build response
        response = {
            "text": transcribed_text,
            "language": language,
            "file_size": file_size,
            "filename": file.filename,
            "processing_time_ms": round(processing_time, 2)
        }
        
        # Add confidence if requested
        if return_confidence:
            response["confidence"] = final_result.get("confidence", None)
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("stt_file_transcription_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"STT file transcription failed: {str(e)}"
        )


@app.post("/stt/transcribe-batch")
async def transcribe_batch(request: BatchSTTRequest):
    """Transcribe multiple audio files in batch.
    
    Request body:
        {
            "audio_files": ["<base64-1>", "<base64-2>", ...],
            "language": "en",
            "sample_rate": 16000,
            "return_confidence": false
        }
    
    Returns:
        {
            "transcriptions": [
                {"text": "transcribed text 1", "confidence": 0.95},
                {"text": "transcribed text 2", "confidence": 0.92}
            ],
            "language": "en",
            "total": 2,
            "processing_time_ms": 456.78
        }
    """
    from app.pipeline.stt import STTFactory
    from app.utils.model_scanner import ModelScanner
    import time
    import base64
    
    try:
        # Get available STT languages
        scanner = ModelScanner()
        available_stt_languages = scanner.get_available_stt_languages()
        
        # Check if language is supported
        if request.language not in available_stt_languages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": f"Language '{request.language}' is not supported for STT",
                    "available_languages": list(available_stt_languages.keys()),
                    "message": "Check /languages/supported for available STT languages"
                }
            )
        
        # Get STT engine
        stt_engine = STTFactory.get_engine(request.language)
        
        # Transcribe all audio files
        start_time = time.time()
        transcriptions = []
        
        for idx, audio_data_b64 in enumerate(request.audio_files):
            try:
                # Decode base64 audio data
                audio_bytes = base64.b64decode(audio_data_b64)
                
                # Create recognizer for this audio
                recognizer = stt_engine.create_recognizer()
                
                # Transcribe
                result = await stt_engine.recognize_async(audio_bytes, recognizer)
                final_result = stt_engine.finalize(recognizer)
                
                # Extract text
                transcribed_text = final_result.get("text", "")
                
                transcription_item = {
                    "text": transcribed_text,
                    "index": idx
                }
                
                # Add confidence if requested
                if request.return_confidence:
                    transcription_item["confidence"] = final_result.get("confidence", None)
                
                transcriptions.append(transcription_item)
                
            except Exception as e:
                logger.error(
                    "batch_stt_item_failed",
                    index=idx,
                    error=str(e),
                    exc_info=True
                )
                transcriptions.append({
                    "text": "",
                    "index": idx,
                    "error": str(e)
                })
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(
            "stt_batch_transcribed",
            language=request.language,
            total=len(transcriptions),
            processing_time_ms=round(processing_time, 2)
        )
        
        return {
            "transcriptions": transcriptions,
            "language": request.language,
            "total": len(transcriptions),
            "processing_time_ms": round(processing_time, 2)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("batch_stt_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch STT transcription failed: {str(e)}"
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for client connections."""
    ws_server = get_websocket_server()
    await ws_server.handle_connection(websocket)


def main():
    """Main entry point."""
    # Setup logging
    setup_logging()
    
    logger.info(
        "starting_server",
        host=settings.host,
        port=settings.port,
        debug=settings.debug
    )
    
    # Run server
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
        ws_ping_interval=settings.ws_ping_interval,
        ws_ping_timeout=settings.ws_ping_timeout,
    )


if __name__ == "__main__":
    main()
