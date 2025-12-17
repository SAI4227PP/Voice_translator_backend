# Voice-to-Voice Translator API Documentation

## 📋 Table of Contents
- [Overview](#overview)
- [Base URL](#base-url)
- [REST API Endpoints](#rest-api-endpoints)
- [Authentication](#authentication)
- [WebSocket Connection](#websocket-connection)
- [Message Protocol](#message-protocol)
- [Message Types](#message-types)
- [Error Handling](#error-handling)
- [Rate Limits](#rate-limits)
- [Code Examples](#code-examples)

---

## 🎯 Overview

The Voice-to-Voice Translator API provides real-time audio translation capabilities through WebSocket connections. Users can join translation rooms and receive live translations of audio streams.

**Key Features:**
- Real-time bidirectional audio translation
- Multi-room support
- Multiple language pairs
- Low-latency streaming
- JWT authentication (optional)
- Rate limiting and connection management

---

## 🌐 Base URL

### Development
```
ws://localhost:8000/ws
```

### Production
```
wss://your-domain.com/ws
```

---

## � REST API Endpoints

The API provides several REST endpoints for management and information retrieval.

### Base URL for REST API

**Development:** `http://localhost:8000`  
**Production:** `https://your-domain.com`

---

### 1. Health Check

Get server health status.

**Endpoint:** `GET /health`

**Authentication:** None required

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600,
  "connections": 15,
  "rooms": 3,
  "timestamp": "2025-12-17T10:30:00Z"
}
```

**Status Codes:**
- `200 OK` - Server is healthy
- `503 Service Unavailable` - Server is unhealthy

**cURL Example:**
```bash
curl http://localhost:8000/health
```

---

### 2. Create Authentication Token

Generate a JWT token for WebSocket authentication.

**Endpoint:** `POST /auth/token`

**Authentication:** API Key (optional)

**Headers:**
```
Content-Type: application/json
X-API-Key: your-api-key (optional)
```

**Request Body:**
```json
{
  "user_id": "user123",
  "name": "John Doe",
  "metadata": {
    "email": "john@example.com"
  }
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | string | Yes | Unique user identifier |
| `name` | string | Yes | User display name |
| `metadata` | object | No | Additional user metadata |

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "user123"
}
```

**Status Codes:**
- `200 OK` - Token created successfully
- `400 Bad Request` - Invalid request body
- `401 Unauthorized` - Invalid API key
- `429 Too Many Requests` - Rate limit exceeded

**cURL Example:**
```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "user_id": "user123",
    "name": "John Doe"
  }'
```

---

### 3. Verify Token

Verify a JWT token's validity.

**Endpoint:** `POST /auth/verify`

**Authentication:** None required

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "valid": true,
  "user_id": "user123",
  "expires_at": "2025-12-17T11:30:00Z"
}
```

**Status Codes:**
- `200 OK` - Token is valid
- `401 Unauthorized` - Token is invalid or expired

**cURL Example:**
```bash
curl -X POST http://localhost:8000/auth/verify \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

---

### 4. Get Supported Languages

Retrieve list of supported languages.

**Endpoint:** `GET /languages`

**Authentication:** None required

**Response:**
```json
{
  "languages": [
    {
      "code": "en",
      "name": "English",
      "stt_available": true,
      "translation_available": true,
      "tts_available": true
    },
    {
      "code": "es",
      "name": "Spanish",
      "stt_available": true,
      "translation_available": true,
      "tts_available": true
    },
    {
      "code": "fr",
      "name": "French",
      "stt_available": true,
      "translation_available": true,
      "tts_available": true
    }
  ],
  "total": 9
}
```

**Status Codes:**
- `200 OK` - Languages retrieved successfully

**cURL Example:**
```bash
curl http://localhost:8000/languages/supported
```

---

### 5. Get Available Translation Pairs

Get list of available language translation pairs.

**Endpoint:** `GET /languages/pairs`

**Authentication:** None required

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | string | No | Filter by source language |
| `target` | string | No | Filter by target language |

**Response:**
```json
{
  "pairs": [
    {
      "source": "en",
      "target": "es",
      "available": true
    },
    {
      "source": "en",
      "target": "fr",
      "available": true
    },
    {
      "source": "es",
      "target": "en",
      "available": true
    }
  ],
  "total": 72
}
```

**Status Codes:**
- `200 OK` - Pairs retrieved successfully

**cURL Example:**
```bash
curl "http://localhost:8000/languages/pairs?source=en"
```

---

### 6. Create Room

Create a new translation room.

**Endpoint:** `POST /rooms`

**Authentication:** JWT Token or API Key

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "room_id": "meeting-room-123",
  "name": "Team Meeting",
  "max_users": 10,
  "languages": ["en", "es", "fr"],
  "settings": {
    "auto_translate": true,
    "record_session": false
  }
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `room_id` | string | No | Custom room ID (auto-generated if not provided) |
| `name` | string | Yes | Room display name |
| `max_users` | integer | No | Maximum users (default: 10) |
| `languages` | array | No | Allowed languages (all if not specified) |
| `settings` | object | No | Room configuration |

**Response:**
```json
{
  "room_id": "meeting-room-123",
  "name": "Team Meeting",
  "created_at": "2025-12-17T10:30:00Z",
  "max_users": 10,
  "current_users": 0,
  "websocket_url": "ws://localhost:8000/ws"
}
```

**Status Codes:**
- `201 Created` - Room created successfully
- `400 Bad Request` - Invalid request body
- `401 Unauthorized` - Authentication required
- `409 Conflict` - Room ID already exists

**cURL Example:**
```bash
curl -X POST http://localhost:8000/rooms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Team Meeting",
    "max_users": 10,
    "languages": ["en", "es"]
  }'
```

---

### 7. Get Room Information

Get details about a specific room.

**Endpoint:** `GET /rooms/{room_id}`

**Authentication:** JWT Token or API Key

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `room_id` | string | Yes | Room identifier |

**Response:**
```json
{
  "room_id": "meeting-room-123",
  "name": "Team Meeting",
  "created_at": "2025-12-17T10:30:00Z",
  "max_users": 10,
  "current_users": 3,
  "users": [
    {
      "user_id": "user_abc123",
      "name": "Alice",
      "language": "en",
      "connected_at": "2025-12-17T10:31:00Z"
    },
    {
      "user_id": "user_def456",
      "name": "Bob",
      "language": "es",
      "connected_at": "2025-12-17T10:32:00Z"
    }
  ],
  "active": true
}
```

**Status Codes:**
- `200 OK` - Room found
- `401 Unauthorized` - Authentication required
- `404 Not Found` - Room does not exist

**cURL Example:**
```bash
curl http://localhost:8000/rooms/meeting-room-123 \
  -H "Authorization: Bearer <token>"
```

---

### 8. List All Rooms

Get list of all active rooms.

**Endpoint:** `GET /rooms`

**Authentication:** JWT Token or API Key

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number (default: 1) |
| `limit` | integer | No | Items per page (default: 20, max: 100) |
| `active` | boolean | No | Filter by active status |

**Response:**
```json
{
  "rooms": [
    {
      "room_id": "meeting-room-123",
      "name": "Team Meeting",
      "current_users": 3,
      "max_users": 10,
      "active": true,
      "created_at": "2025-12-17T10:30:00Z"
    },
    {
      "room_id": "conference-456",
      "name": "Conference Call",
      "current_users": 5,
      "max_users": 20,
      "active": true,
      "created_at": "2025-12-17T09:15:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "limit": 20,
  "pages": 1
}
```

**Status Codes:**
- `200 OK` - Rooms retrieved successfully
- `401 Unauthorized` - Authentication required

**cURL Example:**
```bash
curl "http://localhost:8000/rooms?page=1&limit=20" \
  -H "Authorization: Bearer <token>"
```

---

### 9. Delete Room

Delete a room and disconnect all users.

**Endpoint:** `DELETE /rooms/{room_id}`

**Authentication:** JWT Token or API Key (Admin)

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `room_id` | string | Yes | Room identifier |

**Response:**
```json
{
  "success": true,
  "room_id": "meeting-room-123",
  "message": "Room deleted successfully",
  "disconnected_users": 3
}
```

**Status Codes:**
- `200 OK` - Room deleted successfully
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Room does not exist

**cURL Example:**
```bash
curl -X DELETE http://localhost:8000/rooms/meeting-room-123 \
  -H "Authorization: Bearer <token>"
```

---

### 10. Get Server Statistics

Get server statistics and metrics.

**Endpoint:** `GET /stats`

**Authentication:** JWT Token or API Key

**Response:**
```json
{
  "server": {
    "uptime": 86400,
    "version": "1.0.0",
    "environment": "production"
  },
  "connections": {
    "total": 150,
    "active": 142,
    "idle": 8
  },
  "rooms": {
    "total": 25,
    "active": 20,
    "empty": 5
  },
  "workers": {
    "translation": {
      "total": 4,
      "busy": 2,
      "queue_size": 5
    },
    "tts": {
      "total": 2,
      "busy": 1,
      "queue_size": 3
    }
  },
  "processing": {
    "total_translations": 5420,
    "total_audio_processed_mb": 2850,
    "avg_latency_ms": 245
  },
  "timestamp": "2025-12-17T10:30:00Z"
}
```

**Status Codes:**
- `200 OK` - Statistics retrieved successfully
- `401 Unauthorized` - Authentication required

**cURL Example:**
```bash
curl http://localhost:8000/stats \
  -H "Authorization: Bearer <token>"
```

---

### 11. Text-Only Translation

Translate text without audio processing.

**Endpoint:** `POST /translate`

**Authentication:** JWT Token or API Key

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "text": "Hello, how are you?",
  "source_language": "en",
  "target_language": "es"
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | Text to translate |
| `source_language` | string | Yes | Source language code |
| `target_language` | string | Yes | Target language code |

**Response:**
```json
{
  "original_text": "Hello, how are you?",
  "translated_text": "Hola, ¿cómo estás?",
  "source_language": "en",
  "target_language": "es",
  "processing_time_ms": 45
}
```

**Status Codes:**
- `200 OK` - Translation successful
- `400 Bad Request` - Invalid request body
- `401 Unauthorized` - Authentication required
- `422 Unprocessable Entity` - Unsupported language pair

**cURL Example:**
```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "text": "Hello, how are you?",
    "source_language": "en",
    "target_language": "es"
  }'
```

---

### 12. Batch Translation

Translate multiple texts in one request.

**Endpoint:** `POST /translate/batch`

**Authentication:** JWT Token or API Key

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "texts": [
    "Hello, how are you?",
    "What time is it?",
    "Thank you very much"
  ],
  "source_language": "en",
  "target_language": "es"
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `texts` | array | Yes | Array of texts to translate (max 100) |
| `source_language` | string | Yes | Source language code |
| `target_language` | string | Yes | Target language code |

**Response:**
```json
{
  "translations": [
    {
      "original": "Hello, how are you?",
      "translated": "Hola, ¿cómo estás?",
      "index": 0
    },
    {
      "original": "What time is it?",
      "translated": "¿Qué hora es?",
      "index": 1
    },
    {
      "original": "Thank you very much",
      "translated": "Muchas gracias",
      "index": 2
    }
  ],
  "total": 3,
  "source_language": "en",
  "target_language": "es",
  "processing_time_ms": 120
}
```

**Status Codes:**
- `200 OK` - Translations successful
- `400 Bad Request` - Invalid request body or too many texts
- `401 Unauthorized` - Authentication required
- `422 Unprocessable Entity` - Unsupported language pair

**cURL Example:**
```bash
curl -X POST http://localhost:8000/translate/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "texts": ["Hello", "Goodbye", "Thank you"],
    "source_language": "en",
    "target_language": "es"
  }'
```

---

### 13. Download TTS Audio

Generate and download TTS audio for text.

**Endpoint:** `POST /tts/generate`

**Authentication:** JWT Token or API Key

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "text": "Hello, this is a test message",
  "language": "en",
  "format": "wav"
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | Text to synthesize |
| `language` | string | Yes | Language code |
| `format` | string | No | Audio format: "wav", "mp3" (default: "wav") |

**Response:**
- Content-Type: `audio/wav` or `audio/mpeg`
- Body: Binary audio data

**Status Codes:**
- `200 OK` - Audio generated successfully
- `400 Bad Request` - Invalid request body
- `401 Unauthorized` - Authentication required
- `422 Unprocessable Entity` - Unsupported language

**cURL Example:**
```bash
curl -X POST http://localhost:8000/tts/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "text": "Hello world",
    "language": "en"
  }' \
  --output output.wav
```

---

### 14. System Configuration

Get current system configuration (Admin only).

**Endpoint:** `GET /config`

**Authentication:** JWT Token (Admin)

**Response:**
```json
{
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 4096,
    "format": "PCM16"
  },
  "limits": {
    "max_connections": 100,
    "max_connections_per_ip": 10,
    "max_users_per_room": 10,
    "max_message_size": 10485760
  },
  "rate_limits": {
    "messages_per_second": 10,
    "requests_per_minute": 100
  },
  "workers": {
    "translation_workers": 4,
    "tts_workers": 2
  },
  "features": {
    "authentication_enabled": false,
    "rate_limiting_enabled": true,
    "metrics_enabled": true
  }
}
```

**Status Codes:**
- `200 OK` - Configuration retrieved
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Admin access required

**cURL Example:**
```bash
curl http://localhost:8000/config \
  -H "Authorization: Bearer <admin-token>"
```

---

### REST API Response Format

All REST API responses follow this format:

**Success Response:**
```json
{
  // Response data
}
```

**Error Response:**
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {
      // Additional error details
    }
  }
}
```

---

## �🔐 Authentication

### Optional JWT Authentication

If authentication is enabled (`ENABLE_AUTH=true`), include the JWT token in the WebSocket connection URL:

```
ws://localhost:8000/ws?token=YOUR_JWT_TOKEN
```

### Obtaining a Token

**Endpoint:** `POST /auth/token`

**Request Body:**
```json
{
  "user_id": "user123",
  "name": "John Doe"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### API Key Authentication

Alternatively, use an API key in the query parameter:

```
ws://localhost:8000/ws?api_key=YOUR_API_KEY
```

---

## 🔌 WebSocket Connection

### Connecting

**JavaScript Example:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connected to translation server');
};

ws.onmessage = (event) => {
  if (typeof event.data === 'string') {
    // Text message (JSON)
    const message = JSON.parse(event.data);
    handleMessage(message);
  } else {
    // Binary message (audio data)
    handleAudioData(event.data);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from server');
};
```

**Python Example:**
```python
import asyncio
import websockets
import json

async def connect():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # Send message
        message = {
            "type": "join_room",
            "payload": {
                "room_id": "room123",
                "user_name": "Alice",
                "language": "en"
            }
        }
        await websocket.send(json.dumps(message))
        
        # Receive messages
        async for message in websocket:
            if isinstance(message, str):
                data = json.loads(message)
                print(f"Received: {data}")
            else:
                print(f"Received audio: {len(message)} bytes")

asyncio.run(connect())
```

### Connection Limits

- **Max connections per IP:** 10 (configurable)
- **Max concurrent connections:** 100 (configurable)
- **Connection timeout:** 300 seconds (idle)

---

## 📨 Message Protocol

### Message Structure

All text messages are JSON with the following structure:

```json
{
  "type": "MESSAGE_TYPE",
  "payload": {
    // Type-specific data
  },
  "timestamp": "2025-12-17T10:30:00Z"
}
```

### Message Flow

```
Client → Server: Text Messages (JSON)
Server → Client: Text Messages (JSON)
Client → Server: Binary Messages (Audio Data)
Server → Client: Binary Messages (Audio Data)
```

---

## 📝 Message Types

### 1. JOIN_ROOM

Join a translation room.

**Direction:** Client → Server

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `room_id` | string | Yes | Room identifier |
| `user_name` | string | Yes | User display name |
| `language` | string | Yes | User's language code (e.g., "en", "es", "fr") |

**Example:**
```json
{
  "type": "join_room",
  "payload": {
    "room_id": "room123",
    "user_name": "Alice",
    "language": "en"
  }
}
```

**Response:**
```json
{
  "type": "room_joined",
  "payload": {
    "room_id": "room123",
    "user_id": "user_abc123",
    "users": [
      {
        "user_id": "user_abc123",
        "name": "Alice",
        "language": "en"
      },
      {
        "user_id": "user_def456",
        "name": "Bob",
        "language": "es"
      }
    ]
  },
  "timestamp": "2025-12-17T10:30:00Z"
}
```

---

### 2. LEAVE_ROOM

Leave the current room.

**Direction:** Client → Server

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `room_id` | string | Yes | Room identifier to leave |

**Example:**
```json
{
  "type": "leave_room",
  "payload": {
    "room_id": "room123"
  }
}
```

**Response:**
```json
{
  "type": "room_left",
  "payload": {
    "room_id": "room123",
    "user_id": "user_abc123"
  },
  "timestamp": "2025-12-17T10:35:00Z"
}
```

---

### 3. AUDIO_START

Notify that audio streaming will begin.

**Direction:** Client → Server

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `room_id` | string | Yes | Room identifier |
| `audio_config` | object | No | Audio configuration |
| `audio_config.sample_rate` | integer | No | Sample rate in Hz (default: 16000) |
| `audio_config.channels` | integer | No | Number of channels (default: 1) |
| `audio_config.format` | string | No | Audio format (default: "PCM16") |

**Example:**
```json
{
  "type": "audio_start",
  "payload": {
    "room_id": "room123",
    "audio_config": {
      "sample_rate": 16000,
      "channels": 1,
      "format": "PCM16"
    }
  }
}
```

**Response:**
```json
{
  "type": "audio_started",
  "payload": {
    "room_id": "room123",
    "user_id": "user_abc123",
    "status": "ready"
  },
  "timestamp": "2025-12-17T10:31:00Z"
}
```

---

### 4. AUDIO_DATA (Binary)

Send audio data for translation.

**Direction:** Client → Server (Binary)

**Format:** Raw PCM16 audio bytes

**Requirements:**
- Format: PCM16 (16-bit signed integer)
- Sample Rate: 16000 Hz (configurable)
- Channels: 1 (mono)
- Chunk Size: 4096 bytes (recommended)

**JavaScript Example:**
```javascript
// Capture audio from microphone
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    const mediaRecorder = new MediaRecorder(stream);
    
    mediaRecorder.ondataavailable = (event) => {
      // Convert to PCM16 and send
      const audioData = convertToPCM16(event.data);
      ws.send(audioData);
    };
    
    mediaRecorder.start(100); // Send every 100ms
  });
```

**Python Example:**
```python
import pyaudio

# Audio configuration
CHUNK = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

audio = pyaudio.PyAudio()
stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK
)

# Send audio chunks
while True:
    audio_data = stream.read(CHUNK)
    await websocket.send(audio_data)
```

---

### 5. AUDIO_STOP

Notify that audio streaming has stopped.

**Direction:** Client → Server

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `room_id` | string | Yes | Room identifier |

**Example:**
```json
{
  "type": "audio_stop",
  "payload": {
    "room_id": "room123"
  }
}
```

**Response:**
```json
{
  "type": "audio_stopped",
  "payload": {
    "room_id": "room123",
    "user_id": "user_abc123"
  },
  "timestamp": "2025-12-17T10:32:00Z"
}
```

---

### 6. TRANSLATION_RESULT

Receive translated text.

**Direction:** Server → Client

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `original_text` | string | Original recognized text |
| `translated_text` | string | Translated text |
| `source_language` | string | Source language code |
| `target_language` | string | Target language code |
| `source_user_id` | string | User who spoke |

**Example:**
```json
{
  "type": "translation_result",
  "payload": {
    "original_text": "Hello, how are you?",
    "translated_text": "Hola, ¿cómo estás?",
    "source_language": "en",
    "target_language": "es",
    "source_user_id": "user_abc123"
  },
  "timestamp": "2025-12-17T10:31:15Z"
}
```

---

### 7. TRANSLATED_AUDIO (Binary)

Receive translated audio.

**Direction:** Server → Client (Binary)

**Format:** Raw PCM16 audio bytes ready for playback

**JavaScript Example:**
```javascript
ws.onmessage = (event) => {
  if (event.data instanceof Blob) {
    // Binary audio data
    playAudio(event.data);
  }
};

function playAudio(audioBlob) {
  const audioContext = new AudioContext();
  const reader = new FileReader();
  
  reader.onload = (e) => {
    audioContext.decodeAudioData(e.target.result, (buffer) => {
      const source = audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(audioContext.destination);
      source.start();
    });
  };
  
  reader.readAsArrayBuffer(audioBlob);
}
```

---

### 8. USER_JOINED

Notification when a user joins the room.

**Direction:** Server → Client

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Room identifier |
| `user_id` | string | New user's ID |
| `user_name` | string | New user's name |
| `language` | string | New user's language |

**Example:**
```json
{
  "type": "user_joined",
  "payload": {
    "room_id": "room123",
    "user_id": "user_def456",
    "user_name": "Bob",
    "language": "es"
  },
  "timestamp": "2025-12-17T10:30:30Z"
}
```

---

### 9. USER_LEFT

Notification when a user leaves the room.

**Direction:** Server → Client

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Room identifier |
| `user_id` | string | User who left |

**Example:**
```json
{
  "type": "user_left",
  "payload": {
    "room_id": "room123",
    "user_id": "user_def456"
  },
  "timestamp": "2025-12-17T10:35:00Z"
}
```

---

### 10. PING / PONG

Heartbeat messages to keep connection alive.

**Direction:** Bidirectional

**PING (Server → Client):**
```json
{
  "type": "ping",
  "payload": {},
  "timestamp": "2025-12-17T10:31:00Z"
}
```

**PONG (Client → Server):**
```json
{
  "type": "pong",
  "payload": {},
  "timestamp": "2025-12-17T10:31:00Z"
}
```

**Configuration:**
- Ping interval: 30 seconds (default)
- Ping timeout: 10 seconds (default)

---

### 11. ERROR

Error message from server.

**Direction:** Server → Client

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `error_code` | string | Error code identifier |
| `message` | string | Human-readable error message |
| `details` | object | Additional error details (optional) |

**Example:**
```json
{
  "type": "error",
  "payload": {
    "error_code": "ROOM_FULL",
    "message": "Room has reached maximum capacity",
    "details": {
      "room_id": "room123",
      "max_users": 10,
      "current_users": 10
    }
  },
  "timestamp": "2025-12-17T10:30:00Z"
}
```

**Common Error Codes:**
- `AUTH_FAILED`: Authentication failed
- `ROOM_NOT_FOUND`: Room does not exist
- `ROOM_FULL`: Room at maximum capacity
- `INVALID_MESSAGE`: Malformed message
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `UNSUPPORTED_LANGUAGE`: Language not supported
- `AUDIO_PROCESSING_ERROR`: Audio processing failed

---

## ⚠️ Error Handling

### Client-Side Error Handling

```javascript
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  // Attempt reconnection
  setTimeout(() => reconnect(), 5000);
};

ws.onclose = (event) => {
  if (event.code === 1008) {
    console.error('Connection closed: Rate limit exceeded');
  } else if (event.code === 1000) {
    console.log('Connection closed normally');
  } else {
    console.log('Connection closed unexpectedly:', event.code);
    // Attempt reconnection
    setTimeout(() => reconnect(), 5000);
  }
};
```

### Close Codes

| Code | Description |
|------|-------------|
| 1000 | Normal closure |
| 1001 | Going away |
| 1008 | Policy violation (rate limit) |
| 1011 | Internal server error |

---

## 🚦 Rate Limits

### Connection Limits

| Limit Type | Default Value | Configurable |
|------------|---------------|--------------|
| Max connections per IP | 10 | Yes |
| Max total connections | 100 | Yes |
| Connection timeout | 300 seconds | Yes |

### Message Limits

| Limit Type | Default Value | Configurable |
|------------|---------------|--------------|
| Messages per second | 10 per connection | Yes |
| Requests per minute | 100 per user | Yes |
| Audio chunk size | 10 MB | Yes |

### Rate Limit Headers

Rate limit information is included in error responses:

```json
{
  "type": "error",
  "payload": {
    "error_code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "details": {
      "limit": 100,
      "remaining": 0,
      "reset_at": "2025-12-17T10:31:00Z"
    }
  }
}
```

---

## 💻 Code Examples

### Complete Client Example (JavaScript)

```javascript
class VoiceTranslatorClient {
  constructor(url, options = {}) {
    this.url = url;
    this.ws = null;
    this.roomId = null;
    this.userId = null;
    this.options = {
      language: options.language || 'en',
      userName: options.userName || 'Anonymous',
      ...options
    };
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);
      
      this.ws.onopen = () => {
        console.log('Connected to translation server');
        resolve();
      };
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };
      
      this.ws.onmessage = (event) => {
        this.handleMessage(event);
      };
      
      this.ws.onclose = () => {
        console.log('Disconnected from server');
        this.reconnect();
      };
    });
  }

  handleMessage(event) {
    if (typeof event.data === 'string') {
      const message = JSON.parse(event.data);
      
      switch (message.type) {
        case 'room_joined':
          this.userId = message.payload.user_id;
          this.onRoomJoined(message.payload);
          break;
        case 'translation_result':
          this.onTranslation(message.payload);
          break;
        case 'user_joined':
          this.onUserJoined(message.payload);
          break;
        case 'user_left':
          this.onUserLeft(message.payload);
          break;
        case 'error':
          this.onError(message.payload);
          break;
        case 'ping':
          this.sendPong();
          break;
      }
    } else {
      // Binary audio data
      this.onAudioReceived(event.data);
    }
  }

  async joinRoom(roomId) {
    this.roomId = roomId;
    
    const message = {
      type: 'join_room',
      payload: {
        room_id: roomId,
        user_name: this.options.userName,
        language: this.options.language
      }
    };
    
    this.send(message);
  }

  async startAudio() {
    const message = {
      type: 'audio_start',
      payload: {
        room_id: this.roomId,
        audio_config: {
          sample_rate: 16000,
          channels: 1,
          format: 'PCM16'
        }
      }
    };
    
    this.send(message);
    
    // Start capturing audio
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.startAudioCapture(stream);
  }

  startAudioCapture(stream) {
    const audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    
    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);
      const pcm16 = this.convertToPCM16(inputData);
      this.ws.send(pcm16);
    };
    
    source.connect(processor);
    processor.connect(audioContext.destination);
  }

  convertToPCM16(float32Array) {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16Array.buffer;
  }

  stopAudio() {
    const message = {
      type: 'audio_stop',
      payload: {
        room_id: this.roomId
      }
    };
    
    this.send(message);
  }

  leaveRoom() {
    const message = {
      type: 'leave_room',
      payload: {
        room_id: this.roomId
      }
    };
    
    this.send(message);
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  sendPong() {
    this.send({ type: 'pong', payload: {} });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }

  reconnect() {
    setTimeout(() => {
      console.log('Attempting to reconnect...');
      this.connect();
    }, 5000);
  }

  // Event handlers (override these)
  onRoomJoined(data) {
    console.log('Joined room:', data);
  }

  onTranslation(data) {
    console.log('Translation:', data.translated_text);
  }

  onAudioReceived(audioData) {
    console.log('Received audio:', audioData.byteLength, 'bytes');
    // Play the audio
  }

  onUserJoined(data) {
    console.log('User joined:', data.user_name);
  }

  onUserLeft(data) {
    console.log('User left:', data.user_id);
  }

  onError(error) {
    console.error('Error:', error.message);
  }
}

// Usage
const client = new VoiceTranslatorClient('ws://localhost:8000/ws', {
  language: 'en',
  userName: 'Alice'
});

await client.connect();
await client.joinRoom('room123');
await client.startAudio();
```

---

### Complete Client Example (Python)

```python
import asyncio
import websockets
import json
import pyaudio

class VoiceTranslatorClient:
    def __init__(self, url, language='en', user_name='Anonymous'):
        self.url = url
        self.language = language
        self.user_name = user_name
        self.ws = None
        self.room_id = None
        self.user_id = None
        self.running = False

    async def connect(self):
        self.ws = await websockets.connect(self.url)
        print('Connected to translation server')
        
        # Start message handler
        asyncio.create_task(self.message_handler())

    async def message_handler(self):
        async for message in self.ws:
            if isinstance(message, str):
                data = json.loads(message)
                await self.handle_message(data)
            else:
                await self.handle_audio(message)

    async def handle_message(self, message):
        msg_type = message.get('type')
        payload = message.get('payload', {})
        
        if msg_type == 'room_joined':
            self.user_id = payload.get('user_id')
            print(f"Joined room: {payload.get('room_id')}")
        elif msg_type == 'translation_result':
            print(f"Translation: {payload.get('translated_text')}")
        elif msg_type == 'user_joined':
            print(f"User joined: {payload.get('user_name')}")
        elif msg_type == 'user_left':
            print(f"User left: {payload.get('user_id')}")
        elif msg_type == 'error':
            print(f"Error: {payload.get('message')}")
        elif msg_type == 'ping':
            await self.send_pong()

    async def handle_audio(self, audio_data):
        print(f"Received audio: {len(audio_data)} bytes")
        # Play audio here

    async def join_room(self, room_id):
        self.room_id = room_id
        
        message = {
            'type': 'join_room',
            'payload': {
                'room_id': room_id,
                'user_name': self.user_name,
                'language': self.language
            }
        }
        
        await self.send(message)

    async def start_audio(self):
        message = {
            'type': 'audio_start',
            'payload': {
                'room_id': self.room_id,
                'audio_config': {
                    'sample_rate': 16000,
                    'channels': 1,
                    'format': 'PCM16'
                }
            }
        }
        
        await self.send(message)
        
        # Start audio capture
        asyncio.create_task(self.capture_audio())

    async def capture_audio(self):
        CHUNK = 4096
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        self.running = True
        
        while self.running:
            audio_data = stream.read(CHUNK)
            await self.ws.send(audio_data)
            await asyncio.sleep(0.01)
        
        stream.stop_stream()
        stream.close()
        audio.terminate()

    async def stop_audio(self):
        self.running = False
        
        message = {
            'type': 'audio_stop',
            'payload': {
                'room_id': self.room_id
            }
        }
        
        await self.send(message)

    async def leave_room(self):
        message = {
            'type': 'leave_room',
            'payload': {
                'room_id': self.room_id
            }
        }
        
        await self.send(message)

    async def send(self, message):
        await self.ws.send(json.dumps(message))

    async def send_pong(self):
        await self.send({'type': 'pong', 'payload': {}})

    async def disconnect(self):
        await self.ws.close()

# Usage
async def main():
    client = VoiceTranslatorClient(
        'ws://localhost:8000/ws',
        language='en',
        user_name='Alice'
    )
    
    await client.connect()
    await client.join_room('room123')
    await client.start_audio()
    
    # Keep running for 60 seconds
    await asyncio.sleep(60)
    
    await client.stop_audio()
    await client.leave_room()
    await client.disconnect()

asyncio.run(main())
```

---

## 🌍 Supported Languages

| Language Code | Language Name |
|---------------|---------------|
| `en` | English |
| `hi` | Hindi |
| `te` | Telugu |
| `ta` | Tamil |
| `kn` | Kannada |
| `ml` | Malayalam |
| `gu` | Gujarati |
| `mr` | Marathi |
| `bn` | Bengali |
| `es` | Spanish |
| `fr` | French |
| `de` | German |
| `it` | Italian |
| `pt` | Portuguese |
| `ru` | Russian |
| `zh` | Chinese |
| `ja` | Japanese |

**Primary Focus:** Indian languages (Hindi, Telugu, Tamil, Kannada, Malayalam, Gujarati, Marathi, Bengali)

**Note:** Language support depends on installed models. Check available languages with the `/languages` endpoint.

---

## 📊 Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600,
  "connections": 15,
  "rooms": 3
}
```

---

## 🔧 Configuration

Environment variables to customize API behavior:

```bash
# Server
HOST=0.0.0.0
PORT=8000

# Audio
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_CHUNK_SIZE=4096

# Security
ENABLE_AUTH=false
JWT_SECRET_KEY=your-secret-key
API_KEYS=key1,key2,key3

# Rate Limiting
MAX_CONNECTIONS_PER_IP=10
MAX_MESSAGES_PER_SECOND=10
MAX_REQUESTS_PER_MINUTE=100

# Workers
TRANSLATION_WORKERS=4
TTS_WORKERS=2

# Models
VOSK_MODEL_PATH_EN=models/vosk-en
ARGOS_MODEL_PATH=models/argos
COQUI_MODEL_PATH=models/coqui
```

---

## 🐛 Troubleshooting

### Connection Issues

**Problem:** Cannot connect to WebSocket

**Solutions:**
- Verify the server is running
- Check firewall settings
- Ensure correct URL (ws:// for HTTP, wss:// for HTTPS)
- Verify authentication token if required

### Audio Issues

**Problem:** No audio being received

**Solutions:**
- Check audio format (must be PCM16, 16kHz, mono)
- Verify microphone permissions
- Ensure audio chunks are correct size
- Check rate limits not exceeded

### Translation Issues

**Problem:** Translations not working

**Solutions:**
- Verify language models are installed
- Check language codes are supported
- Ensure room has users with different languages
- Check server logs for errors

---

## 📞 Support

For issues and questions:
- GitHub Issues: [your-repo/issues]
- Email: support@your-domain.com
- Documentation: [your-docs-url]

---

## 📄 License

This API documentation is part of the Voice-to-Voice Translator project.

**Version:** 1.0.0  
**Last Updated:** December 17, 2025
