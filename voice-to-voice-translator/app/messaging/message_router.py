"""
Message router for handling and dispatching WebSocket messages.
"""
from typing import Dict, Any, Optional
from app.config import get_logger
from app.messaging.protocol import (
    MessageType,
    create_error_message,
    create_room_joined_message,
    create_user_joined_message,
    create_user_left_message,
    create_pong_message
)
from app.rooms import get_room_manager
from app.server.connection_manager import get_connection_manager

logger = get_logger(__name__)


class MessageRouter:
    """Routes WebSocket messages to appropriate handlers."""
    
    def __init__(self):
        """Initialize message router."""
        self.room_manager = get_room_manager()
        self.connection_manager = get_connection_manager()
        
        # Message handlers mapping
        self.handlers = {
            MessageType.JOIN_ROOM: self._handle_join_room,
            MessageType.LEAVE_ROOM: self._handle_leave_room,
            MessageType.AUDIO_START: self._handle_audio_start,
            MessageType.AUDIO_STOP: self._handle_audio_stop,
            MessageType.TEXT_MESSAGE: self._handle_text_message,
            MessageType.GET_ROOM_INFO: self._handle_get_room_info,
            MessageType.PING: self._handle_ping,
        }
        
        logger.info("message_router_initialized")
    
    async def route_message(self, connection_id: str, message: dict) -> None:
        """Route a message to its handler.
        
        Args:
            connection_id: Connection identifier
            message: Message dictionary
        """
        message_type = message.get("type")
        
        if not message_type:
            logger.warning("message_missing_type", connection_id=connection_id)
            return
        
        try:
            # Get handler for message type
            handler = self.handlers.get(message_type)
            
            if handler:
                await handler(connection_id, message.get("payload", {}))
            else:
                logger.warning(
                    "unknown_message_type",
                    connection_id=connection_id,
                    message_type=message_type
                )
        
        except Exception as e:
            logger.error(
                "message_routing_error",
                connection_id=connection_id,
                message_type=message_type,
                error=str(e),
                exc_info=True
            )
    
    async def route_binary(self, connection_id: str, data: bytes) -> None:
        """Route binary message (audio data).
        
        Args:
            connection_id: Connection identifier
            data: Binary data
        """
        # TODO: Implement audio processing
        # 1. Extract header (user_id, sequence, timestamp)
        # 2. Get user's room
        # 3. Process through pipeline (STT → Translation → TTS)
        # 4. Send to target users
        logger.debug(
            "binary_message_routed",
            connection_id=connection_id,
            size=len(data)
        )
    
    async def _handle_join_room(self, connection_id: str, payload: dict) -> None:
        """Handle join room message.
        
        Args:
            connection_id: Connection identifier
            payload: Message payload
        """
        room_id = payload.get("room_id")
        user_id = payload.get("user_id")
        username = payload.get("username")
        source_lang = payload.get("source_lang")
        target_lang = payload.get("target_lang")
        
        if not all([room_id, user_id, username, source_lang, target_lang]):
            logger.warning("join_room_missing_fields", connection_id=connection_id)
            return
        
        # Register user connection
        self.connection_manager.register_user(user_id, connection_id)
        
        # Add user to room
        success = self.room_manager.add_user_to_room(
            room_id, user_id, username, source_lang, target_lang
        )
        
        if not success:
            # Room full
            error_msg = create_error_message(
                "ROOM_FULL",
                "Room has reached maximum capacity"
            )
            await self.connection_manager.send_to_user(user_id, error_msg)
            return
        
        # Add to connection manager room tracking
        self.connection_manager.add_to_room(room_id, user_id)
        
        # Get room info
        room = self.room_manager.get_room(room_id)
        users_data = [user.to_dict() for user in room.get_all_users()]
        
        # Send room joined confirmation to user
        join_msg = create_room_joined_message(room_id, user_id, users_data)
        await self.connection_manager.send_to_user(user_id, join_msg)
        
        # Broadcast user joined to other room members
        user_data = {
            "user_id": user_id,
            "username": username,
            "source_lang": source_lang,
            "target_lang": target_lang
        }
        joined_msg = create_user_joined_message(room_id, user_data)
        await self.connection_manager.send_to_room(
            room_id, joined_msg, exclude_user=user_id
        )
        
        logger.info(
            "user_joined_room",
            room_id=room_id,
            user_id=user_id,
            username=username
        )
    
    async def _handle_leave_room(self, connection_id: str, payload: dict) -> None:
        """Handle leave room message.
        
        Args:
            connection_id: Connection identifier
            payload: Message payload
        """
        room_id = payload.get("room_id")
        user_id = payload.get("user_id")
        
        if not all([room_id, user_id]):
            return
        
        await self._leave_room(room_id, user_id)
    
    async def _leave_room(self, room_id: str, user_id: str) -> None:
        """Internal leave room handler.
        
        Args:
            room_id: Room identifier
            user_id: User identifier
        """
        # Get user info before removal
        room = self.room_manager.get_room(room_id)
        if not room:
            return
        
        user = room.get_user(user_id)
        username = user.username if user else "Unknown"
        
        # Remove from room
        self.room_manager.remove_user_from_room(room_id, user_id)
        self.connection_manager.remove_from_room(room_id, user_id)
        
        # Broadcast user left to remaining members
        left_msg = create_user_left_message(room_id, user_id, username)
        await self.connection_manager.send_to_room(room_id, left_msg)
        
        logger.info("user_left_room", room_id=room_id, user_id=user_id)
    
    async def _handle_audio_start(self, connection_id: str, payload: dict) -> None:
        """Handle audio start message.
        
        Args:
            connection_id: Connection identifier
            payload: Message payload
        """
        room_id = payload.get("room_id")
        user_id = payload.get("user_id")
        
        logger.info("audio_started", room_id=room_id, user_id=user_id)
        
        # TODO: Initialize audio pipeline for user
        # Send acknowledgment
        ack_msg = {
            "type": MessageType.AUDIO_START_ACK.value,
            "payload": {
                "room_id": room_id,
                "user_id": user_id,
                "ready": True
            }
        }
        await self.connection_manager.send_to_user(user_id, ack_msg)
    
    async def _handle_audio_stop(self, connection_id: str, payload: dict) -> None:
        """Handle audio stop message.
        
        Args:
            connection_id: Connection identifier
            payload: Message payload
        """
        room_id = payload.get("room_id")
        user_id = payload.get("user_id")
        
        logger.info("audio_stopped", room_id=room_id, user_id=user_id)
        
        # TODO: Cleanup audio pipeline for user
        # Send acknowledgment
        ack_msg = {
            "type": MessageType.AUDIO_STOP_ACK.value,
            "payload": {
                "room_id": room_id,
                "user_id": user_id
            }
        }
        await self.connection_manager.send_to_user(user_id, ack_msg)
    
    async def _handle_text_message(self, connection_id: str, payload: dict) -> None:
        """Handle text message.
        
        Args:
            connection_id: Connection identifier
            payload: Message payload
        """
        room_id = payload.get("room_id")
        user_id = payload.get("user_id")
        text = payload.get("text")
        
        logger.debug("text_message", room_id=room_id, user_id=user_id)
        
        # Broadcast to room
        msg = {
            "type": MessageType.TEXT_MESSAGE.value,
            "payload": payload
        }
        await self.connection_manager.send_to_room(room_id, msg)
    
    async def _handle_get_room_info(self, connection_id: str, payload: dict) -> None:
        """Handle get room info message.
        
        Args:
            connection_id: Connection identifier
            payload: Message payload
        """
        room_id = payload.get("room_id")
        
        room_info = self.room_manager.get_room_info(room_id)
        
        if room_info:
            msg = {
                "type": MessageType.ROOM_INFO.value,
                "payload": room_info
            }
        else:
            msg = create_error_message(
                "ROOM_NOT_FOUND",
                f"Room '{room_id}' does not exist"
            )
        
        # Find user for this connection
        for user_id, conn_id in self.connection_manager.user_connections.items():
            if conn_id == connection_id:
                await self.connection_manager.send_to_user(user_id, msg)
                break
    
    async def _handle_ping(self, connection_id: str, payload: dict) -> None:
        """Handle ping message.
        
        Args:
            connection_id: Connection identifier
            payload: Message payload
        """
        # Send pong response
        pong_msg = create_pong_message()
        
        # Find user for this connection
        for user_id, conn_id in self.connection_manager.user_connections.items():
            if conn_id == connection_id:
                await self.connection_manager.send_to_user(user_id, pong_msg)
                break
    
    async def handle_user_disconnect(self, user_id: str) -> None:
        """Handle user disconnection.
        
        Args:
            user_id: User identifier
        """
        # Remove user from all rooms
        rooms = self.room_manager.remove_user_from_all_rooms(user_id)
        
        # Broadcast to affected rooms
        for room_id in rooms:
            left_msg = create_user_left_message(room_id, user_id, "Unknown")
            await self.connection_manager.send_to_room(room_id, left_msg)
        
        logger.info("user_disconnected", user_id=user_id, affected_rooms=rooms)


# Global message router instance
message_router = MessageRouter()


def get_message_router() -> MessageRouter:
    """Get the global message router instance.
    
    Returns:
        MessageRouter instance
    """
    return message_router
