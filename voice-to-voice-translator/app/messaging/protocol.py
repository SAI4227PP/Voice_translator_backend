"""
WebSocket message protocol definitions.
"""
from enum import Enum
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class MessageType(str, Enum):
    """WebSocket message types."""
    
    # Client → Server
    JOIN_ROOM = "join_room"
    LEAVE_ROOM = "leave_room"
    AUDIO_START = "audio_start"
    AUDIO_STOP = "audio_stop"
    TEXT_MESSAGE = "text_message"
    PING = "ping"
    GET_ROOM_INFO = "get_room_info"
    
    # Server → Client
    ROOM_JOINED = "room_joined"
    ROOM_LEFT = "room_left"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    TRANSCRIPTION = "transcription"
    TRANSLATION = "translation"
    AUDIO_START_ACK = "audio_start_ack"
    AUDIO_STOP_ACK = "audio_stop_ack"
    PONG = "pong"
    ROOM_INFO = "room_info"
    ERROR = "error"


class Message(BaseModel):
    """Base message structure."""
    
    type: MessageType
    payload: Dict[str, Any]
    timestamp: Optional[str] = None
    message_id: Optional[str] = None
    
    class Config:
        use_enum_values = True


# Message payload models

class JoinRoomPayload(BaseModel):
    """Join room message payload."""
    room_id: str
    user_id: str
    username: str
    source_lang: str
    target_lang: str


class LeaveRoomPayload(BaseModel):
    """Leave room message payload."""
    room_id: str
    user_id: str


class AudioStartPayload(BaseModel):
    """Audio start message payload."""
    room_id: str
    user_id: str
    audio_config: Optional[Dict[str, Any]] = None


class AudioStopPayload(BaseModel):
    """Audio stop message payload."""
    room_id: str
    user_id: str


class TextMessagePayload(BaseModel):
    """Text message payload."""
    room_id: str
    user_id: str
    text: str
    lang: str


class TranscriptionPayload(BaseModel):
    """Transcription result payload."""
    room_id: str
    user_id: str
    text: str
    lang: str
    is_final: bool = False
    confidence: Optional[float] = None


class TranslationPayload(BaseModel):
    """Translation result payload."""
    room_id: str
    source_user_id: str
    target_user_id: Optional[str] = None
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    confidence: Optional[float] = None


class ErrorPayload(BaseModel):
    """Error message payload."""
    code: str
    message: str
    details: Optional[str] = None
    recoverable: bool = True


# Message creation functions

def create_message(
    message_type: MessageType,
    payload: Dict[str, Any],
    message_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a message dictionary.
    
    Args:
        message_type: Type of message
        payload: Message payload
        message_id: Optional message ID
        
    Returns:
        Message dictionary
    """
    return {
        "type": message_type.value,
        "payload": payload,
        "timestamp": datetime.now().isoformat(),
        "message_id": message_id or str(uuid.uuid4())
    }


def create_error_message(
    error_code: str,
    message: str,
    details: Optional[str] = None,
    recoverable: bool = True
) -> Dict[str, Any]:
    """Create an error message.
    
    Args:
        error_code: Error code
        message: Error message
        details: Optional error details
        recoverable: Whether error is recoverable
        
    Returns:
        Error message dictionary
    """
    return create_message(
        MessageType.ERROR,
        {
            "code": error_code,
            "message": message,
            "details": details,
            "recoverable": recoverable
        }
    )


def create_room_joined_message(
    room_id: str,
    user_id: str,
    users: list
) -> Dict[str, Any]:
    """Create room joined message.
    
    Args:
        room_id: Room identifier
        user_id: User identifier
        users: List of users in room
        
    Returns:
        Message dictionary
    """
    return create_message(
        MessageType.ROOM_JOINED,
        {
            "room_id": room_id,
            "user_id": user_id,
            "users": users
        }
    )


def create_user_joined_message(room_id: str, user: dict) -> Dict[str, Any]:
    """Create user joined message.
    
    Args:
        room_id: Room identifier
        user: User data dictionary
        
    Returns:
        Message dictionary
    """
    return create_message(
        MessageType.USER_JOINED,
        {
            "room_id": room_id,
            "user": user
        }
    )


def create_user_left_message(
    room_id: str,
    user_id: str,
    username: str
) -> Dict[str, Any]:
    """Create user left message.
    
    Args:
        room_id: Room identifier
        user_id: User identifier
        username: Username
        
    Returns:
        Message dictionary
    """
    return create_message(
        MessageType.USER_LEFT,
        {
            "room_id": room_id,
            "user_id": user_id,
            "username": username
        }
    )


def create_transcription_message(
    room_id: str,
    user_id: str,
    text: str,
    lang: str,
    is_final: bool = False,
    confidence: Optional[float] = None
) -> Dict[str, Any]:
    """Create transcription message.
    
    Args:
        room_id: Room identifier
        user_id: User identifier
        text: Transcribed text
        lang: Language code
        is_final: Whether transcription is final
        confidence: Optional confidence score
        
    Returns:
        Message dictionary
    """
    return create_message(
        MessageType.TRANSCRIPTION,
        {
            "room_id": room_id,
            "user_id": user_id,
            "text": text,
            "lang": lang,
            "is_final": is_final,
            "confidence": confidence
        }
    )


def create_translation_message(
    room_id: str,
    source_user_id: str,
    target_user_id: str,
    original_text: str,
    translated_text: str,
    source_lang: str,
    target_lang: str,
    confidence: Optional[float] = None
) -> Dict[str, Any]:
    """Create translation message.
    
    Args:
        room_id: Room identifier
        source_user_id: Source user identifier
        target_user_id: Target user identifier
        original_text: Original text
        translated_text: Translated text
        source_lang: Source language code
        target_lang: Target language code
        confidence: Optional confidence score
        
    Returns:
        Message dictionary
    """
    return create_message(
        MessageType.TRANSLATION,
        {
            "room_id": room_id,
            "source_user_id": source_user_id,
            "target_user_id": target_user_id,
            "original_text": original_text,
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "confidence": confidence
        }
    )


def create_pong_message() -> Dict[str, Any]:
    """Create pong message.
    
    Returns:
        Message dictionary
    """
    return create_message(
        MessageType.PONG,
        {"timestamp": datetime.now().isoformat()}
    )
