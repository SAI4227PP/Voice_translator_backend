# WebSocket Protocol

## Overview

The Voice-to-Voice Translator uses a WebSocket-based protocol for real-time bidirectional communication between clients and the server. Messages are exchanged in JSON format (text) and raw audio data (binary).

## Connection Endpoint

```
ws://host:port/ws
```

### Connection Parameters

Query parameters (optional):
- `token`: JWT authentication token (if auth enabled)
- `client_id`: Unique client identifier

Example:
```
ws://localhost:8000/ws?token=eyJhbGc...&client_id=client123
```

## Message Types

All text messages follow this structure:

```json
{
  "type": "message_type",
  "payload": { ... },
  "timestamp": "2025-12-17T10:30:00Z",
  "message_id": "uuid-v4"
}
```

### Client → Server Messages

#### 1. JOIN_ROOM

Join or create a translation room.

```json
{
  "type": "join_room",
  "payload": {
    "room_id": "room123",
    "user_id": "user1",
    "username": "John Doe",
    "source_lang": "en",
    "target_lang": "hi"
  }
}
```

**Fields**:
- `room_id`: Unique room identifier
- `user_id`: Unique user identifier
- `username`: Display name
- `source_lang`: User's speaking language (ISO 639-1 code)
- `target_lang`: Desired translation language

**Response**: `ROOM_JOINED` or `ERROR`

#### 2. LEAVE_ROOM

Leave current room.

```json
{
  "type": "leave_room",
  "payload": {
    "room_id": "room123",
    "user_id": "user1"
  }
}
```

**Response**: `ROOM_LEFT` or `ERROR`

#### 3. AUDIO_START

Signal start of audio stream.

```json
{
  "type": "audio_start",
  "payload": {
    "room_id": "room123",
    "user_id": "user1",
    "audio_config": {
      "sample_rate": 16000,
      "channels": 1,
      "format": "PCM16",
      "chunk_size": 4096
    }
  }
}
```

**Response**: `AUDIO_START_ACK`

#### 4. AUDIO_STOP

Signal end of audio stream.

```json
{
  "type": "audio_stop",
  "payload": {
    "room_id": "room123",
    "user_id": "user1"
  }
}
```

**Response**: `AUDIO_STOP_ACK`

#### 5. TEXT_MESSAGE

Send text message (for chat or corrections).

```json
{
  "type": "text_message",
  "payload": {
    "room_id": "room123",
    "user_id": "user1",
    "text": "Hello, how are you?",
    "lang": "en"
  }
}
```

**Response**: `TEXT_MESSAGE` (broadcast to room)

#### 6. PING

Heartbeat message.

```json
{
  "type": "ping",
  "payload": {}
}
```

**Response**: `PONG`

#### 7. GET_ROOM_INFO

Request current room state.

```json
{
  "type": "get_room_info",
  "payload": {
    "room_id": "room123"
  }
}
```

**Response**: `ROOM_INFO`

### Server → Client Messages

#### 1. ROOM_JOINED

Confirmation of room join.

```json
{
  "type": "room_joined",
  "payload": {
    "room_id": "room123",
    "user_id": "user1",
    "users": [
      {
        "user_id": "user1",
        "username": "John Doe",
        "source_lang": "en",
        "target_lang": "hi"
      },
      {
        "user_id": "user2",
        "username": "Jane Smith",
        "source_lang": "hi",
        "target_lang": "en"
      }
    ]
  }
}
```

#### 2. ROOM_LEFT

Confirmation of room leave.

```json
{
  "type": "room_left",
  "payload": {
    "room_id": "room123",
    "user_id": "user1"
  }
}
```

#### 3. USER_JOINED

Broadcast when another user joins.

```json
{
  "type": "user_joined",
  "payload": {
    "room_id": "room123",
    "user": {
      "user_id": "user2",
      "username": "Jane Smith",
      "source_lang": "hi",
      "target_lang": "en"
    }
  }
}
```

#### 4. USER_LEFT

Broadcast when another user leaves.

```json
{
  "type": "user_left",
  "payload": {
    "room_id": "room123",
    "user_id": "user2",
    "username": "Jane Smith"
  }
}
```

#### 5. TRANSCRIPTION

Intermediate transcription result (from STT).

```json
{
  "type": "transcription",
  "payload": {
    "room_id": "room123",
    "user_id": "user1",
    "text": "Hello how are you",
    "lang": "en",
    "is_final": false,
    "confidence": 0.85
  }
}
```

#### 6. TRANSLATION

Translation result.

```json
{
  "type": "translation",
  "payload": {
    "room_id": "room123",
    "source_user_id": "user1",
    "target_user_id": "user2",
    "original_text": "Hello, how are you?",
    "translated_text": "नमस्ते, आप कैसे हैं?",
    "source_lang": "en",
    "target_lang": "hi",
    "confidence": 0.92
  }
}
```

#### 7. AUDIO_START_ACK

Acknowledgment of audio start.

```json
{
  "type": "audio_start_ack",
  "payload": {
    "room_id": "room123",
    "user_id": "user1",
    "ready": true
  }
}
```

#### 8. AUDIO_STOP_ACK

Acknowledgment of audio stop.

```json
{
  "type": "audio_stop_ack",
  "payload": {
    "room_id": "room123",
    "user_id": "user1"
  }
}
```

#### 9. PONG

Heartbeat response.

```json
{
  "type": "pong",
  "payload": {
    "timestamp": "2025-12-17T10:30:00Z"
  }
}
```

#### 10. ROOM_INFO

Room state information.

```json
{
  "type": "room_info",
  "payload": {
    "room_id": "room123",
    "created_at": "2025-12-17T10:00:00Z",
    "users": [ ... ],
    "active_speakers": ["user1"],
    "supported_languages": ["en", "hi"]
  }
}
```

#### 11. ERROR

Error notification.

```json
{
  "type": "error",
  "payload": {
    "code": "INVALID_ROOM",
    "message": "Room does not exist",
    "details": "Room 'room123' not found",
    "recoverable": true
  }
}
```

**Error Codes**:
- `INVALID_ROOM`: Room not found
- `ROOM_FULL`: Maximum users reached
- `INVALID_MESSAGE`: Malformed message
- `AUTH_FAILED`: Authentication failed
- `RATE_LIMIT`: Too many requests
- `INTERNAL_ERROR`: Server error
- `UNSUPPORTED_LANGUAGE`: Language not available
- `AUDIO_ERROR`: Audio processing error

## Binary Audio Messages

Audio data is sent as binary WebSocket frames.

### Client → Server (Audio Input)

Binary message structure:
```
[Header (16 bytes)][Audio Data (variable)]
```

**Header Format**:
- Bytes 0-7: User ID (UTF-8, padded)
- Bytes 8-11: Sequence number (uint32, big-endian)
- Bytes 12-15: Timestamp (uint32, milliseconds)

**Audio Data**:
- Format: PCM16 (16-bit signed integer)
- Sample Rate: 16000 Hz (configurable)
- Channels: 1 (mono)
- Byte Order: Little-endian

### Server → Client (Translated Audio)

Binary message structure:
```
[Header (24 bytes)][Audio Data (variable)]
```

**Header Format**:
- Bytes 0-7: Source User ID (UTF-8, padded)
- Bytes 8-15: Target User ID (UTF-8, padded)
- Bytes 16-19: Sequence number (uint32, big-endian)
- Bytes 20-23: Timestamp (uint32, milliseconds)

**Audio Data**:
- Same format as input

## Connection Lifecycle

### 1. Connection Establishment

```
Client                          Server
  │                               │
  ├─────── WebSocket Connect ────►│
  │                               │
  │◄────── Connection Open ───────┤
  │                               │
```

### 2. Room Join

```
Client                          Server
  │                               │
  ├────────── JOIN_ROOM ─────────►│
  │                               │
  │◄───────── ROOM_JOINED ────────┤
  │                               │
  │◄───────── USER_JOINED ────────┤ (broadcast to others)
  │                               │
```

### 3. Audio Streaming

```
Client                          Server                     Other Client
  │                               │                              │
  ├───── AUDIO_START ────────────►│                              │
  │                               │                              │
  │◄──── AUDIO_START_ACK ─────────┤                              │
  │                               │                              │
  ├─── Binary Audio Chunk 1 ─────►│                              │
  ├─── Binary Audio Chunk 2 ─────►│                              │
  │                               │                              │
  │◄─────── TRANSCRIPTION ────────┤                              │
  │                               │                              │
  │◄─────── TRANSLATION ──────────┤                              │
  │                               │                              │
  │                               ├───► Binary Audio Chunk ─────►│
  │                               │                              │
  ├───── AUDIO_STOP ─────────────►│                              │
  │                               │                              │
  │◄──── AUDIO_STOP_ACK ──────────┤                              │
  │                               │                              │
```

### 4. Disconnection

```
Client                          Server
  │                               │
  ├────────── LEAVE_ROOM ────────►│
  │                               │
  │◄───────── ROOM_LEFT ──────────┤
  │                               │
  ├─────── Close Connection ─────►│
  │                               │
  │◄─────── Close Confirm ────────┤
  │                               │
```

## Rate Limiting

Default limits:
- Join room: 10 requests per minute
- Audio streaming: Unlimited (quality-based throttling)
- Text messages: 30 per minute
- Room info requests: 60 per minute

## Reconnection Strategy

1. **Exponential Backoff**: 1s, 2s, 4s, 8s, 16s, 30s (max)
2. **Session Recovery**: Send previous `room_id` and `user_id` on reconnect
3. **State Sync**: Server sends current room state after reconnection

## Best Practices

### Client Implementation

1. **Always send AUDIO_START before binary audio**
2. **Buffer audio before sending** (minimum 100ms chunks)
3. **Include sequence numbers** for ordering
4. **Handle ERROR messages** gracefully
5. **Implement heartbeat** (PING every 30 seconds)
6. **Reconnect automatically** on disconnect

### Server Implementation

1. **Validate all messages** before processing
2. **Broadcast state changes** to all room members
3. **Clean up resources** on disconnect
4. **Log all errors** with context
5. **Rate limit** per connection and IP

## Example Client Flow (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

// Connect
ws.onopen = () => {
  // Join room
  ws.send(JSON.stringify({
    type: 'join_room',
    payload: {
      room_id: 'room123',
      user_id: 'user1',
      username: 'John',
      source_lang: 'en',
      target_lang: 'hi'
    }
  }));
};

// Handle messages
ws.onmessage = (event) => {
  if (event.data instanceof Blob) {
    // Binary audio data
    handleAudio(event.data);
  } else {
    // JSON message
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  }
};

// Send audio
function sendAudio(audioBuffer) {
  ws.send(audioBuffer);
}
```

## Security Considerations

1. **Always use WSS (WebSocket Secure)** in production
2. **Validate JWT tokens** if authentication enabled
3. **Sanitize user inputs** (usernames, room IDs)
4. **Implement rate limiting** to prevent abuse
5. **Monitor connection count** to prevent DoS
6. **Encrypt sensitive data** in messages
