# System Architecture

## Overview

The Voice-to-Voice Translator is a real-time translation system designed for low-latency voice communication across language barriers. The architecture emphasizes modularity, scalability, and performance.

## High-Level Architecture

```
┌─────────────┐         WebSocket          ┌──────────────────┐
│   Client    │◄──────────────────────────►│  WebSocket       │
│   (Web/App) │      Audio Streaming       │  Server          │
└─────────────┘                             └────────┬─────────┘
                                                     │
                                            ┌────────▼─────────┐
                                            │  Connection      │
                                            │  Manager         │
                                            └────────┬─────────┘
                                                     │
                                            ┌────────▼─────────┐
                                            │  Room            │
                                            │  Manager         │
                                            └────────┬─────────┘
                                                     │
                                      ┌──────────────┼──────────────┐
                                      │              │              │
                                ┌─────▼─────┐  ┌────▼────┐  ┌─────▼─────┐
                                │    STT    │  │ Translate│  │    TTS    │
                                │  Engine   │  │  Engine  │  │  Engine   │
                                └───────────┘  └──────────┘  └───────────┘
                                      │              │              │
                                      └──────────────┼──────────────┘
                                                     │
                                            ┌────────▼─────────┐
                                            │  Pipeline        │
                                            │  Manager         │
                                            └──────────────────┘
```

## Core Components

### 1. WebSocket Server Layer

**Purpose**: Handle real-time bidirectional communication with clients

**Components**:
- **websocket_server.py**: Main WebSocket endpoint handler
- **connection_manager.py**: Manages active connections and routing
- **heartbeat.py**: Connection health monitoring

**Key Features**:
- Async/await architecture using FastAPI/Uvicorn
- Automatic reconnection handling
- Message queue for reliable delivery
- Connection state management

### 2. Room Management Layer

**Purpose**: Organize users into translation sessions

**Components**:
- **room_manager.py**: Central room orchestration
- **room.py**: Individual room logic and state

**Key Features**:
- Multi-user support per room
- Language pair management
- Audio stream routing
- Session persistence

### 3. Processing Pipeline Layer

**Purpose**: Execute the translation pipeline

**Components**:

#### Speech-to-Text (STT)
- **vosk_engine.py**: Vosk model integration
- **stt_factory.py**: STT engine abstraction

#### Translation
- **argos_engine.py**: Argos Translate integration
- **translator.py**: Translation orchestration

#### Text-to-Speech (TTS)
- **coqui_engine.py**: Coqui TTS integration
- **tts_factory.py**: TTS engine abstraction

**Pipeline Flow**:
```
Audio Chunk → STT → Text → Translation → Translated Text → TTS → Audio Chunk
```

### 4. Audio Processing Layer

**Purpose**: Handle audio buffer management and validation

**Components**:
- **audio_buffer.py**: Buffering and chunking
- **audio_utils.py**: Audio format conversions
- **pcm_validator.py**: Audio quality validation

### 5. Messaging Layer

**Purpose**: Define and route WebSocket messages

**Components**:
- **protocol.py**: Message schema definitions
- **message_router.py**: Message dispatch logic

### 6. Security Layer

**Purpose**: Authentication and rate limiting

**Components**:
- **auth.py**: JWT authentication (optional)
- **rate_limiter.py**: Request throttling

### 7. Worker Layer

**Purpose**: Background task processing

**Components**:
- **translation_worker.py**: Async translation processing
- **tts_worker.py**: Async TTS generation

## Data Flow

### Incoming Audio Stream

```
1. Client sends audio chunk (WebSocket binary)
2. Connection Manager receives and validates
3. Audio Buffer accumulates chunks
4. When sufficient data: Pipeline triggered
5. STT processes audio → text
6. Translation engine translates text
7. TTS generates audio from translated text
8. Audio routed to target user(s) in room
9. WebSocket sends audio chunk to client(s)
```

### Connection Lifecycle

```
1. Client connects to WebSocket endpoint
2. Authentication (if enabled)
3. Client sends JOIN_ROOM message
4. Room Manager assigns to room
5. Connection Manager tracks connection
6. Heartbeat begins
7. Audio streaming active
8. On disconnect: cleanup and notify room
```

## Technology Stack

### Core Framework
- **FastAPI**: Modern async web framework
- **Uvicorn**: ASGI server
- **WebSockets**: Real-time communication

### ML Models
- **Vosk**: Offline speech recognition
- **Argos Translate**: Offline translation
- **Coqui TTS**: Neural text-to-speech

### Audio Processing
- **NumPy**: Numerical processing
- **SoundFile**: Audio I/O

### Utilities
- **Pydantic**: Data validation
- **Structlog**: Structured logging
- **asyncio**: Async operations

## Scalability Considerations

### Horizontal Scaling
- Stateless server design
- Redis for shared state (optional)
- Load balancer for multiple instances

### Vertical Scaling
- Multi-threading for CPU-bound tasks
- GPU acceleration for models
- Memory-mapped model loading

### Performance Optimization
- Model warm-up on startup
- Connection pooling
- Audio chunk batching
- Worker pool for parallel processing

## Deployment Architectures

### Single Server
```
┌──────────────────────────┐
│   Application Server     │
│  - WebSocket Handler     │
│  - All ML Models         │
│  - Room Manager          │
└──────────────────────────┘
```

### Microservices
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Gateway    │────►│  STT Service │────►│ Translation  │
│   Server     │     │              │     │   Service    │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                                           ┌──────▼───────┐
                                           │ TTS Service  │
                                           └──────────────┘
```

## Security Architecture

### Authentication Flow
```
1. Client requests token (username/password)
2. Server validates credentials
3. JWT token issued
4. Token included in WebSocket connection
5. Token validated on each message
```

### Rate Limiting
- Per-connection limits
- Per-IP limits
- Adaptive throttling

## Monitoring and Observability

### Metrics
- Connection count
- Message throughput
- Pipeline latency
- Error rates
- Model inference time

### Logging
- Structured JSON logs
- Request tracing
- Error tracking
- Performance profiling

## Failure Handling

### Network Failures
- Automatic reconnection
- Message queue persistence
- Graceful degradation

### Model Failures
- Fallback models
- Error reporting
- Partial results

### Resource Exhaustion
- Connection limits
- Memory management
- Queue bounds

## Extension Points

### Adding New Languages
1. Download Vosk model for language
2. Download Argos translation package
3. Download/train TTS model
4. Update configuration
5. Restart server

### Custom STT/TTS Engines
1. Implement engine interface
2. Add to factory
3. Configure via settings
4. No code changes needed elsewhere

### Plugin Architecture
- Message middleware
- Custom audio processors
- Analytics hooks
- Storage backends
