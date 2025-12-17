# Integration Guide - Complete Backend

## 🎯 Overview

This guide shows how all modules integrate together to form a complete voice-to-voice translation system.

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Server                           │
│                          (main.py)                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Security   │  │  WebSocket   │  │    Rooms     │
│              │  │    Server    │  │   Manager    │
│ • Auth       │  │              │  │              │
│ • Rate Limit │  │ • Connection │  │ • Multi-room │
└──────────────┘  │ • Heartbeat  │  │ • Users      │
                  └──────┬───────┘  └──────┬───────┘
                         │                 │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │    Message      │
                         │    Router       │
                         └────────┬────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
                ▼                 ▼                 ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │    Audio     │  │   Pipeline   │  │   Workers    │
        │              │  │   Manager    │  │              │
        │ • Buffer     │  │              │  │ • Translation│
        │ • Utils      │  │ STT→Trans→TTS│  │ • TTS Pool   │
        │ • Validator  │  │              │  │              │
        └──────────────┘  └──────┬───────┘  └──────────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
                ▼                 ▼                 ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │     STT      │  │ Translation  │  │     TTS      │
        │              │  │              │  │              │
        │ • Vosk       │  │ • Argos      │  │ • Coqui      │
        │ • Factory    │  │ • Translator │  │ • Factory    │
        └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 🔌 Module Integration Flow

### 1. Client Connection Flow

```python
# Client connects via WebSocket
WebSocket Connect
    ↓
Security Check (auth.py, rate_limiter.py)
    ↓
Connection Manager (connection_manager.py)
    ↓
Heartbeat Registration (heartbeat.py)
    ↓
Connection Active
```

**Code Integration:**
```python
# In websocket_server.py
from app.security import get_auth_manager, get_connection_limiter

async def handle_connection(websocket):
    # Security check
    limiter = get_connection_limiter()
    limiter.check_connection_limit(client_ip)
    limiter.register_connection(user_id, client_ip)
    
    # Register connection
    await connection_manager.connect(user_id, websocket)
    
    # Start heartbeat
    heartbeat_manager.register(user_id)
```

---

### 2. Room Join Flow

```python
Client sends JOIN_ROOM message
    ↓
Message Router (message_router.py)
    ↓
Room Manager (room_manager.py)
    ↓
User added to Room (room.py)
    ↓
Confirmation sent to all room users
```

**Code Integration:**
```python
# In message_router.py
from app.rooms import room_manager

async def _handle_join_room(self, message, user_id, websocket):
    # Add user to room
    user = await room_manager.add_user_to_room(
        room_id=room_id,
        user_id=user_id,
        name=name,
        language=language
    )
    
    # Send confirmation
    await connection_manager.send_to_room(room_id, message)
```

---

### 3. Audio Processing Flow

```python
Client sends AUDIO_DATA (binary)
    ↓
Audio Buffer (audio_buffer.py)
    ↓
PCM Validator (pcm_validator.py)
    ↓
Pipeline Manager (pipeline_manager.py)
    ↓
┌─────────────────────────────────────┐
│         Translation Pipeline         │
│                                     │
│  1. STT (vosk_engine.py)           │
│     ↓ Text recognized              │
│  2. Translation (argos_engine.py)  │
│     ↓ Text translated              │
│  3. TTS (coqui_engine.py)         │
│     ↓ Audio synthesized            │
└─────────────────────────────────────┘
    ↓
Workers (translation_worker.py, tts_worker.py)
    ↓
Send translated audio to target users
```

**Code Integration:**
```python
# In message_router.py
from app.audio import AudioBuffer, PCMValidator
from app.pipeline import get_pipeline_manager

async def _handle_audio_data(self, audio_data, user_id):
    # Buffer audio
    buffer = AudioBuffer(chunk_size=4096)
    buffer.add(audio_data)
    
    # Validate
    validator = PCMValidator(sample_rate=16000)
    if not validator.is_valid(audio_data):
        return
    
    # Process through pipeline
    pipeline = get_pipeline_manager()
    result = await pipeline.process_complete_audio(
        audio_data=buffer.get_all(),
        user_id=user_id,
        source_lang=user.language,
        target_lang=target_user.language
    )
    
    # Send translated audio
    await connection_manager.send_binary_to_user(
        target_user.id,
        result.audio_data
    )
```

---

## 🔐 Security Integration

### Rate Limiting

```python
from app.security import get_rate_limiter, get_connection_limiter

# In WebSocket message handler
rate_limiter = get_rate_limiter()
connection_limiter = get_connection_limiter()

# Check connection limit (on connect)
connection_limiter.check_connection_limit(ip_address)
connection_limiter.register_connection(user_id, ip_address)

# Check message rate (on each message)
connection_limiter.check_message_rate(user_id)

# Check API rate limit (on API calls)
rate_limiter.check_rate_limit(user_id)
```

### Authentication

```python
from app.security import get_auth_manager

auth_manager = get_auth_manager()

# Create token
token = auth_manager.create_access_token(user_id)

# Verify token
payload = auth_manager.verify_token(token)
user_id = auth_manager.get_user_id_from_token(token)
```

---

## 👷 Worker Pool Integration

### Translation Workers

```python
from app.workers import get_translation_pool, TranslationTask

# Start pool (in lifespan)
pool = get_translation_pool()
await pool.start()

# Submit task
task = TranslationTask(
    task_id="task_123",
    text="Hello world",
    source_lang="en",
    target_lang="es",
    user_id="user_456",
    callback=translation_callback
)
await pool.submit_task(task)

# Callback receives result
async def translation_callback(result):
    print(f"Translated: {result.translated_text}")
```

### TTS Workers

```python
from app.workers import get_tts_pool, TTSTask

# Start pool
tts_pool = get_tts_pool()
await tts_pool.start()

# Submit task
task = TTSTask(
    task_id="tts_123",
    text="Hola mundo",
    language="es",
    user_id="user_456",
    callback=tts_callback
)
await tts_pool.submit_task(task)

# Callback receives audio
async def tts_callback(result):
    audio_bytes = result.audio_data
    await send_audio_to_client(audio_bytes)
```

---

## 🚀 Complete Usage Example

```python
from fastapi import FastAPI, WebSocket
from app.config import get_settings
from app.server import WebSocketServer
from app.rooms import room_manager
from app.pipeline import get_pipeline_manager
from app.security import get_auth_manager, get_connection_limiter
from app.workers import get_translation_pool, get_tts_pool

app = FastAPI()
settings = get_settings()

@app.on_event("startup")
async def startup():
    # Start worker pools
    translation_pool = get_translation_pool()
    await translation_pool.start()
    
    tts_pool = get_tts_pool()
    await tts_pool.start()

@app.on_event("shutdown")
async def shutdown():
    # Stop worker pools
    translation_pool = get_translation_pool()
    await translation_pool.stop()
    
    tts_pool = get_tts_pool()
    await tts_pool.stop()
    
    # Cleanup rooms
    await room_manager.cleanup()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Security checks
    connection_limiter = get_connection_limiter()
    client_ip = websocket.client.host
    
    try:
        connection_limiter.check_connection_limit(client_ip)
    except RateLimitError:
        await websocket.close(code=1008, reason="Too many connections")
        return
    
    # Handle connection
    ws_server = WebSocketServer()
    await ws_server.handle_connection(websocket)
```

---

## 📝 Configuration

All modules use centralized settings from `app/config/settings.py`:

```python
from app.config import get_settings

settings = get_settings()

# Audio settings
sample_rate = settings.audio_sample_rate  # 16000
chunk_size = settings.audio_chunk_size    # 4096

# Worker settings
translation_workers = settings.translation_workers  # 4
tts_workers = settings.tts_workers                 # 2

# Security settings
max_connections = settings.max_connections_per_ip   # 10
max_messages = settings.max_messages_per_second    # 10

# Rate limiting
requests_per_min = settings.max_requests_per_minute  # 100
```

---

## 🧪 Testing Integration

```python
import pytest
from app.pipeline import get_pipeline_manager
from app.workers import get_translation_pool

@pytest.mark.asyncio
async def test_complete_pipeline():
    # Initialize
    pipeline = get_pipeline_manager()
    pool = get_translation_pool()
    await pool.start()
    
    # Process audio
    result = await pipeline.process_complete_audio(
        audio_data=test_audio,
        user_id="test_user",
        source_lang="en",
        target_lang="es"
    )
    
    # Verify
    assert result.recognized_text
    assert result.translated_text
    assert result.audio_data
    assert result.processing_time_ms < 5000
    
    # Cleanup
    await pool.stop()
```

---

## 🔄 Lifecycle Management

### Application Startup
1. Load configuration (`settings.py`)
2. Initialize logging (`logging.py`)
3. Start worker pools (`translation_worker.py`, `tts_worker.py`)
4. Initialize pipeline manager (`pipeline_manager.py`)
5. Load AI models (Vosk, Argos, Coqui)
6. Start FastAPI server (`main.py`)

### Request Handling
1. Accept WebSocket connection
2. Authenticate (if enabled)
3. Check rate limits
4. Register connection
5. Start heartbeat
6. Route messages
7. Process audio through pipeline
8. Send results to target users

### Application Shutdown
1. Stop accepting new connections
2. Close existing connections gracefully
3. Stop worker pools
4. Cleanup rooms
5. Release model resources
6. Flush logs

---

## 📊 Monitoring Points

```python
# Connection stats
connection_manager.get_active_connections()

# Room stats
room_manager.get_room_count()
room_manager.get_all_rooms()

# Worker stats
translation_pool.get_stats()
tts_pool.get_stats()

# Rate limiter stats
rate_limiter.get_remaining_requests(user_id)
connection_limiter.get_busy_workers()
```

---

## 🎯 Key Integration Points

1. **WebSocket ↔ Security**: Authentication and rate limiting
2. **WebSocket ↔ Rooms**: User management and message routing
3. **Rooms ↔ Pipeline**: Audio processing and translation
4. **Pipeline ↔ Workers**: Parallel processing
5. **Pipeline ↔ Audio**: Buffering and validation
6. **All ↔ Config**: Centralized settings
7. **All ↔ Logging**: Structured logging

---

## ✅ Integration Checklist

- [x] WebSocket server handles connections
- [x] Security middleware validates and rate limits
- [x] Room manager orchestrates multi-room support
- [x] Audio module buffers and validates
- [x] Pipeline manager coordinates STT→Translation→TTS
- [x] Worker pools enable parallel processing
- [x] All modules use centralized configuration
- [x] All modules use structured logging
- [x] Graceful startup and shutdown
- [x] Error handling throughout

---

## 🚀 Ready for Production!

All modules are integrated and work together seamlessly. The system is ready for:
- Load testing
- Performance optimization
- Production deployment

**Integration Status: ✅ COMPLETE**
