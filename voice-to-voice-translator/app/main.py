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
