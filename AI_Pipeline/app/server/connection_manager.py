"""
WebSocket connection manager for handling active connections.
"""
from typing import Dict, Set, Optional
from fastapi import WebSocket
from app.config import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message routing."""
    
    def __init__(self):
        """Initialize connection manager."""
        # Active connections: {websocket_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        
        # User to WebSocket mapping: {user_id: websocket_id}
        self.user_connections: Dict[str, str] = {}
        
        # Room memberships: {room_id: Set[user_id]}
        self.room_members: Dict[str, Set[str]] = {}
        
        logger.info("connection_manager_initialized")
    
    async def connect(self, websocket: WebSocket, connection_id: str) -> None:
        """Accept and register a new WebSocket connection.
        
        Args:
            websocket: WebSocket instance
            connection_id: Unique connection identifier
        """
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(
            "connection_accepted",
            connection_id=connection_id,
            total_connections=len(self.active_connections)
        )
    
    def disconnect(self, connection_id: str) -> Optional[str]:
        """Remove a WebSocket connection.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            User ID if connection was associated with a user, None otherwise
        """
        # Remove from active connections
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        # Find and remove user mapping
        user_id = None
        for uid, conn_id in list(self.user_connections.items()):
            if conn_id == connection_id:
                user_id = uid
                del self.user_connections[uid]
                break
        
        # Remove from rooms
        if user_id:
            for room_id, members in self.room_members.items():
                if user_id in members:
                    members.remove(user_id)
        
        logger.info(
            "connection_disconnected",
            connection_id=connection_id,
            user_id=user_id,
            remaining_connections=len(self.active_connections)
        )
        
        return user_id
    
    def register_user(self, user_id: str, connection_id: str) -> None:
        """Register a user with their connection.
        
        Args:
            user_id: User identifier
            connection_id: Connection identifier
        """
        self.user_connections[user_id] = connection_id
        logger.info("user_registered", user_id=user_id, connection_id=connection_id)
    
    def add_to_room(self, room_id: str, user_id: str) -> None:
        """Add a user to a room.
        
        Args:
            room_id: Room identifier
            user_id: User identifier
        """
        if room_id not in self.room_members:
            self.room_members[room_id] = set()
        
        self.room_members[room_id].add(user_id)
        logger.info(
            "user_added_to_room",
            room_id=room_id,
            user_id=user_id,
            room_size=len(self.room_members[room_id])
        )
    
    def remove_from_room(self, room_id: str, user_id: str) -> None:
        """Remove a user from a room.
        
        Args:
            room_id: Room identifier
            user_id: User identifier
        """
        if room_id in self.room_members and user_id in self.room_members[room_id]:
            self.room_members[room_id].remove(user_id)
            
            # Clean up empty rooms
            if not self.room_members[room_id]:
                del self.room_members[room_id]
            
            logger.info(
                "user_removed_from_room",
                room_id=room_id,
                user_id=user_id
            )
    
    def get_room_members(self, room_id: str) -> Set[str]:
        """Get all members of a room.
        
        Args:
            room_id: Room identifier
            
        Returns:
            Set of user IDs in the room
        """
        return self.room_members.get(room_id, set()).copy()
    
    def get_user_websocket(self, user_id: str) -> Optional[WebSocket]:
        """Get WebSocket connection for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            WebSocket instance or None if not found
        """
        connection_id = self.user_connections.get(user_id)
        if connection_id:
            return self.active_connections.get(connection_id)
        return None
    
    async def send_to_user(self, user_id: str, message: dict) -> bool:
        """Send a message to a specific user.
        
        Args:
            user_id: User identifier
            message: Message dictionary to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        websocket = self.get_user_websocket(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(
                    "send_to_user_failed",
                    user_id=user_id,
                    error=str(e)
                )
                return False
        return False
    
    async def send_to_room(
        self,
        room_id: str,
        message: dict,
        exclude_user: Optional[str] = None
    ) -> int:
        """Send a message to all users in a room.
        
        Args:
            room_id: Room identifier
            message: Message dictionary to send
            exclude_user: Optional user ID to exclude from broadcast
            
        Returns:
            Number of users who received the message
        """
        members = self.get_room_members(room_id)
        if exclude_user:
            members.discard(exclude_user)
        
        sent_count = 0
        for user_id in members:
            if await self.send_to_user(user_id, message):
                sent_count += 1
        
        logger.debug(
            "message_broadcast_to_room",
            room_id=room_id,
            recipients=sent_count,
            total_members=len(members)
        )
        
        return sent_count
    
    async def send_binary_to_user(self, user_id: str, data: bytes) -> bool:
        """Send binary data to a specific user.
        
        Args:
            user_id: User identifier
            data: Binary data to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        websocket = self.get_user_websocket(user_id)
        if websocket:
            try:
                await websocket.send_bytes(data)
                return True
            except Exception as e:
                logger.error(
                    "send_binary_to_user_failed",
                    user_id=user_id,
                    error=str(e)
                )
                return False
        return False
    
    def get_connection_count(self) -> int:
        """Get total number of active connections.
        
        Returns:
            Number of active connections
        """
        return len(self.active_connections)
    
    def get_room_count(self) -> int:
        """Get total number of active rooms.
        
        Returns:
            Number of active rooms
        """
        return len(self.room_members)
    
    def is_user_connected(self, user_id: str) -> bool:
        """Check if a user is currently connected.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if user is connected, False otherwise
        """
        return user_id in self.user_connections


# Global connection manager instance
connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance.
    
    Returns:
        ConnectionManager instance
    """
    return connection_manager
