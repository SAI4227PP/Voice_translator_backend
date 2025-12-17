"""
Main application entry point.
"""
import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import setup_logging, get_settings, logger
from app.server import get_websocket_server

settings = get_settings()


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
    
    # Initialize models and resources here
    # await initialize_models()
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    # Cleanup resources here


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
            "max_message_size": settings.max_message_size
        },
        "rate_limits": {
            "messages_per_second": settings.max_messages_per_second,
            "requests_per_minute": settings.max_requests_per_minute
        },
        "workers": {
            "translation_workers": settings.translation_workers,
            "tts_workers": settings.tts_workers
        },
        "features": {
            "authentication_enabled": settings.enable_auth,
            "rate_limiting_enabled": True,
            "metrics_enabled": settings.enable_metrics
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
