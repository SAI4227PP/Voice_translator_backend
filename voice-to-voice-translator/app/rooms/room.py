"""
Room class for managing individual translation rooms.
"""
from typing import Dict, Set, Optional
from datetime import datetime
from app.config import get_logger

logger = get_logger(__name__)


class User:
    """Represents a user in a room."""
    
    def __init__(
        self,
        user_id: str,
        username: str,
        source_lang: str,
        target_lang: str
    ):
        """Initialize user.
        
        Args:
            user_id: Unique user identifier
            username: Display name
            source_lang: User's speaking language
            target_lang: Desired translation language
        """
        self.user_id = user_id
        self.username = username
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.joined_at = datetime.now()
        self.is_speaking = False
    
    def to_dict(self) -> dict:
        """Convert user to dictionary.
        
        Returns:
            User data as dictionary
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "joined_at": self.joined_at.isoformat(),
            "is_speaking": self.is_speaking
        }


class Room:
    """Represents a translation room."""
    
    def __init__(self, room_id: str, max_users: int = 10):
        """Initialize room.
        
        Args:
            room_id: Unique room identifier
            max_users: Maximum number of users allowed
        """
        self.room_id = room_id
        self.max_users = max_users
        self.created_at = datetime.now()
        self.users: Dict[str, User] = {}
        self.active_speakers: Set[str] = set()
        
        logger.info("room_created", room_id=room_id, max_users=max_users)
    
    def add_user(
        self,
        user_id: str,
        username: str,
        source_lang: str,
        target_lang: str
    ) -> bool:
        """Add a user to the room.
        
        Args:
            user_id: User identifier
            username: Display name
            source_lang: User's speaking language
            target_lang: Desired translation language
            
        Returns:
            True if added successfully, False if room is full
        """
        if len(self.users) >= self.max_users:
            logger.warning(
                "room_full",
                room_id=self.room_id,
                user_id=user_id
            )
            return False
        
        user = User(user_id, username, source_lang, target_lang)
        self.users[user_id] = user
        
        logger.info(
            "user_added_to_room",
            room_id=self.room_id,
            user_id=user_id,
            username=username,
            total_users=len(self.users)
        )
        
        return True
    
    def remove_user(self, user_id: str) -> bool:
        """Remove a user from the room.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if removed, False if user not in room
        """
        if user_id not in self.users:
            return False
        
        # Remove from active speakers
        self.active_speakers.discard(user_id)
        
        # Remove user
        del self.users[user_id]
        
        logger.info(
            "user_removed_from_room",
            room_id=self.room_id,
            user_id=user_id,
            remaining_users=len(self.users)
        )
        
        return True
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            User instance or None
        """
        return self.users.get(user_id)
    
    def get_all_users(self) -> list[User]:
        """Get all users in the room.
        
        Returns:
            List of User instances
        """
        return list(self.users.values())
    
    def set_user_speaking(self, user_id: str, is_speaking: bool) -> None:
        """Set user speaking status.
        
        Args:
            user_id: User identifier
            is_speaking: Whether user is speaking
        """
        if user_id in self.users:
            self.users[user_id].is_speaking = is_speaking
            
            if is_speaking:
                self.active_speakers.add(user_id)
            else:
                self.active_speakers.discard(user_id)
    
    def get_target_users(self, source_user_id: str) -> list[User]:
        """Get users who should receive translation from source user.
        
        Args:
            source_user_id: Source user identifier
            
        Returns:
            List of target users
        """
        source_user = self.get_user(source_user_id)
        if not source_user:
            return []
        
        # Find users whose target language matches source user's language
        target_users = []
        for user in self.users.values():
            if user.user_id != source_user_id:
                # Check if this user wants translation of source user's language
                if user.target_lang == source_user.source_lang:
                    target_users.append(user)
        
        return target_users
    
    def is_empty(self) -> bool:
        """Check if room is empty.
        
        Returns:
            True if no users, False otherwise
        """
        return len(self.users) == 0
    
    def is_full(self) -> bool:
        """Check if room is full.
        
        Returns:
            True if at max capacity, False otherwise
        """
        return len(self.users) >= self.max_users
    
    def get_user_count(self) -> int:
        """Get number of users in room.
        
        Returns:
            User count
        """
        return len(self.users)
    
    def get_languages(self) -> Set[str]:
        """Get all languages used in the room.
        
        Returns:
            Set of language codes
        """
        languages = set()
        for user in self.users.values():
            languages.add(user.source_lang)
            languages.add(user.target_lang)
        return languages
    
    def to_dict(self) -> dict:
        """Convert room to dictionary.
        
        Returns:
            Room data as dictionary
        """
        return {
            "room_id": self.room_id,
            "created_at": self.created_at.isoformat(),
            "max_users": self.max_users,
            "user_count": len(self.users),
            "users": [user.to_dict() for user in self.users.values()],
            "active_speakers": list(self.active_speakers),
            "languages": list(self.get_languages())
        }
