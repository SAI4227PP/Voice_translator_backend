"""
WebSocket server implementation for handling real-time connections.
"""
import uuid
import json
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect, status
from app.config import get_logger
from app.server.connection_manager import get_connection_manager
from app.server.heartbeat import get_heartbeat_manager
from app.messaging.message_router import get_message_router
from app.messaging.protocol import MessageType, create_error_message

logger = get_logger(__name__)


class WebSocketServer:
    """WebSocket server for handling client connections."""
    
    def __init__(self):
        """Initialize WebSocket server."""
        self.connection_manager = get_connection_manager()
        self.heartbeat_manager = get_heartbeat_manager()
        self.message_router = get_message_router()
        
        logger.info("websocket_server_initialized")
    
    async def handle_connection(self, websocket: WebSocket) -> None:
        """Handle a new WebSocket connection.
        
        Args:
            websocket: WebSocket instance
        """
        connection_id = str(uuid.uuid4())
        
        try:
            # Accept connection
            await self.connection_manager.connect(websocket, connection_id)
            
            # Start heartbeat monitoring
            self.heartbeat_manager.start_heartbeat(
                connection_id,
                websocket,
                on_timeout_callback=self._handle_timeout
            )
            
            logger.info(
                "websocket_connection_established",
                connection_id=connection_id
            )
            
            # Main message loop
            await self._message_loop(websocket, connection_id)
        
        except WebSocketDisconnect as e:
            logger.info(
                "websocket_disconnect",
                connection_id=connection_id,
                code=e.code
            )
        
        except Exception as e:
            logger.error(
                "websocket_error",
                connection_id=connection_id,
                error=str(e),
                exc_info=True
            )
        
        finally:
            # Clean up
            await self._cleanup_connection(connection_id)
    
    async def _message_loop(self, websocket: WebSocket, connection_id: str) -> None:
        """Main loop for receiving and processing messages.
        
        Args:
            websocket: WebSocket instance
            connection_id: Connection identifier
        """
        while True:
            # Receive message (text or binary)
            message = await websocket.receive()
            
            # Handle different message types
            if "text" in message:
                await self._handle_text_message(
                    connection_id,
                    message["text"]
                )
            
            elif "bytes" in message:
                await self._handle_binary_message(
                    connection_id,
                    message["bytes"]
                )
            
            elif message.get("type") == "websocket.disconnect":
                logger.info("websocket_client_disconnect", connection_id=connection_id)
                break
    
    async def _handle_text_message(self, connection_id: str, text: str) -> None:
        """Handle incoming text message.
        
        Args:
            connection_id: Connection identifier
            text: Message text (JSON)
        """
        try:
            # Parse JSON message
            message = json.loads(text)
            message_type = message.get("type")
            
            logger.debug(
                "text_message_received",
                connection_id=connection_id,
                message_type=message_type
            )
            
            # Handle pong messages (heartbeat response)
            if message_type == MessageType.PONG:
                self.heartbeat_manager.record_pong(connection_id)
                return
            
            # Route message to appropriate handler
            await self.message_router.route_message(
                connection_id,
                message
            )
        
        except json.JSONDecodeError as e:
            logger.error(
                "invalid_json_message",
                connection_id=connection_id,
                error=str(e)
            )
            await self._send_error(
                connection_id,
                "INVALID_MESSAGE",
                "Invalid JSON format"
            )
        
        except Exception as e:
            logger.error(
                "text_message_error",
                connection_id=connection_id,
                error=str(e),
                exc_info=True
            )
            await self._send_error(
                connection_id,
                "INTERNAL_ERROR",
                "Failed to process message"
            )
    
    async def _handle_binary_message(self, connection_id: str, data: bytes) -> None:
        """Handle incoming binary message (audio data).
        
        Args:
            connection_id: Connection identifier
            data: Binary data
        """
        try:
            logger.debug(
                "binary_message_received",
                connection_id=connection_id,
                size=len(data)
            )
            
            # Route binary message to appropriate handler
            await self.message_router.route_binary(
                connection_id,
                data
            )
        
        except Exception as e:
            logger.error(
                "binary_message_error",
                connection_id=connection_id,
                error=str(e),
                exc_info=True
            )
    
    async def _handle_timeout(self, connection_id: str) -> None:
        """Handle connection timeout.
        
        Args:
            connection_id: Connection identifier
        """
        logger.warning("connection_timeout", connection_id=connection_id)
        
        # Get websocket and close it
        user_id = self.connection_manager.disconnect(connection_id)
        
        if user_id:
            # Notify room members about disconnection
            await self.message_router.handle_user_disconnect(user_id)
    
    async def _send_error(
        self,
        connection_id: str,
        error_code: str,
        message: str
    ) -> None:
        """Send error message to client.
        
        Args:
            connection_id: Connection identifier
            error_code: Error code
            message: Error message
        """
        error_msg = create_error_message(error_code, message)
        
        # Find user for this connection
        for user_id, conn_id in self.connection_manager.user_connections.items():
            if conn_id == connection_id:
                await self.connection_manager.send_to_user(user_id, error_msg)
                break
    
    async def _cleanup_connection(self, connection_id: str) -> None:
        """Clean up connection resources.
        
        Args:
            connection_id: Connection identifier
        """
        logger.info("cleaning_up_connection", connection_id=connection_id)
        
        # Stop heartbeat
        self.heartbeat_manager.stop_heartbeat(connection_id)
        
        # Disconnect from connection manager
        user_id = self.connection_manager.disconnect(connection_id)
        
        # Handle user disconnect in message router
        if user_id:
            await self.message_router.handle_user_disconnect(user_id)
        
        logger.info(
            "connection_cleanup_complete",
            connection_id=connection_id,
            user_id=user_id
        )


# Global WebSocket server instance
websocket_server = WebSocketServer()


def get_websocket_server() -> WebSocketServer:
    """Get the global WebSocket server instance.
    
    Returns:
        WebSocketServer instance
    """
    return websocket_server
