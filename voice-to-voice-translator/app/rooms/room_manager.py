"""
Room manager for handling multiple translation rooms.
"""
from typing import Dict, Optional, List
from app.rooms.room import Room, User
from app.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


class RoomManager:
    """Manages multiple translation rooms."""
    
    def __init__(self):
        """Initialize room manager."""
        self.rooms: Dict[str, Room] = {}
        logger.info("room_manager_initialized")
    
    def create_room(self, room_id: str) -> Room:
        """Create a new room.
        
        Args:
            room_id: Room identifier
            
        Returns:
            Created Room instance
        """
        if room_id in self.rooms:
            logger.info("room_already_exists", room_id=room_id)
            return self.rooms[room_id]
        
        room = Room(room_id, max_users=settings.max_users_per_room)
        self.rooms[room_id] = room
        
        logger.info("room_created", room_id=room_id)
        return room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """Get room by ID.
        
        Args:
            room_id: Room identifier
            
        Returns:
            Room instance or None
        """
        return self.rooms.get(room_id)
    
    def delete_room(self, room_id: str) -> bool:
        """Delete a room.
        
        Args:
            room_id: Room identifier
            
        Returns:
            True if deleted, False if not found
        """
        if room_id in self.rooms:
            del self.rooms[room_id]
            logger.info("room_deleted", room_id=room_id)
            return True
        return False
    
    def get_or_create_room(self, room_id: str) -> Room:
        """Get existing room or create new one.
        
        Args:
            room_id: Room identifier
            
        Returns:
            Room instance
        """
        if room_id not in self.rooms:
            return self.create_room(room_id)
        return self.rooms[room_id]
    
    def add_user_to_room(
        self,
        room_id: str,
        user_id: str,
        username: str,
        source_lang: str,
        target_lang: str
    ) -> bool:
        """Add a user to a room.
        
        Args:
            room_id: Room identifier
            user_id: User identifier
            username: Display name
            source_lang: User's speaking language
            target_lang: Desired translation language
            
        Returns:
            True if added successfully, False otherwise
        """
        room = self.get_or_create_room(room_id)
        return room.add_user(user_id, username, source_lang, target_lang)
    
    def remove_user_from_room(self, room_id: str, user_id: str) -> bool:
        """Remove a user from a room.
        
        Args:
            room_id: Room identifier
            user_id: User identifier
            
        Returns:
            True if removed, False otherwise
        """
        room = self.get_room(room_id)
        if not room:
            return False
        
        removed = room.remove_user(user_id)
        
        # Delete room if empty
        if room.is_empty():
            self.delete_room(room_id)
        
        return removed
    
    def get_user_room(self, user_id: str) -> Optional[Room]:
        """Find which room a user is in.
        
        Args:
            user_id: User identifier
            
        Returns:
            Room instance or None
        """
        for room in self.rooms.values():
            if user_id in room.users:
                return room
        return None
    
    def remove_user_from_all_rooms(self, user_id: str) -> List[str]:
        """Remove a user from all rooms they're in.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of room IDs user was removed from
        """
        removed_from = []
        
        for room_id, room in list(self.rooms.items()):
            if user_id in room.users:
                room.remove_user(user_id)
                removed_from.append(room_id)
                
                # Delete room if empty
                if room.is_empty():
                    self.delete_room(room_id)
        
        if removed_from:
            logger.info(
                "user_removed_from_all_rooms",
                user_id=user_id,
                rooms=removed_from
            )
        
        return removed_from
    
    def get_all_rooms(self) -> List[Room]:
        """Get all active rooms.
        
        Returns:
            List of Room instances
        """
        return list(self.rooms.values())
    
    def get_room_count(self) -> int:
        """Get total number of rooms.
        
        Returns:
            Room count
        """
        return len(self.rooms)
    
    def get_total_users(self) -> int:
        """Get total number of users across all rooms.
        
        Returns:
            Total user count
        """
        return sum(room.get_user_count() for room in self.rooms.values())
    
    def cleanup_empty_rooms(self) -> int:
        """Remove all empty rooms.
        
        Returns:
            Number of rooms deleted
        """
        empty_rooms = [
            room_id for room_id, room in self.rooms.items()
            if room.is_empty()
        ]
        
        for room_id in empty_rooms:
            self.delete_room(room_id)
        
        if empty_rooms:
            logger.info("empty_rooms_cleaned", count=len(empty_rooms))
        
        return len(empty_rooms)
    
    def get_room_info(self, room_id: str) -> Optional[dict]:
        """Get room information as dictionary.
        
        Args:
            room_id: Room identifier
            
        Returns:
            Room data dictionary or None
        """
        room = self.get_room(room_id)
        if room:
            return room.to_dict()
        return None


# Global room manager instance
room_manager = RoomManager()


def get_room_manager() -> RoomManager:
    """Get the global room manager instance.
    
    Returns:
        RoomManager instance
    """
    return room_manager
