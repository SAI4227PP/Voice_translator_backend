# Voice-to-Voice Translator

A real-time voice-to-voice translation system using WebSocket connections for low-latency audio streaming and translation between multiple languages.

## Features

- **Real-time Audio Streaming**: WebSocket-based bidirectional audio communication
- **Multi-language Support**: English and Hindi with extensible language support
- **Low Latency Pipeline**: Optimized STT → Translation → TTS pipeline
- **Room-based Architecture**: Support for multiple concurrent translation sessions
- **Offline Capable**: Uses local models (Vosk, Argos, Coqui TTS)
- **Scalable Design**: Worker-based architecture for handling concurrent users

## Architecture

The system consists of several key components:

1. **WebSocket Server**: Manages real-time connections and audio streaming
2. **Speech-to-Text (STT)**: Vosk-based speech recognition
3. **Translation Engine**: Argos Translate for language translation
4. **Text-to-Speech (TTS)**: Coqui TTS for natural voice synthesis
5. **Room Manager**: Handles multi-user session management
6. **Pipeline Manager**: Orchestrates the complete translation flow

## Prerequisites

- Python 3.9+
- 4GB RAM minimum (8GB recommended)
- 5GB disk space for models
- Linux/Windows/MacOS

## Quick Start

### 1. Clone the repository

```bash
git clone <repository-url>
cd voice-to-voice-translator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Download models

```bash
python scripts/download_models.py
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Run the server

```bash
python app/main.py
```

The server will start on `ws://localhost:8000` by default.

## Configuration

Key configuration options in `.env`:

- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `MAX_CONNECTIONS`: Maximum concurrent connections
- `AUDIO_SAMPLE_RATE`: Audio sample rate (default: 16000)
- `AUDIO_CHUNK_SIZE`: Audio chunk size in bytes

## WebSocket Protocol

Clients connect to the WebSocket endpoint and exchange JSON messages:

```json
{
  "type": "join_room",
  "room_id": "room123",
  "user_id": "user1",
  "source_lang": "en",
  "target_lang": "hi"
}
```

See [docs/websocket-protocol.md](docs/websocket-protocol.md) for complete protocol documentation.

## API Endpoints

- `ws://host:port/ws`: Main WebSocket endpoint
- `http://host:port/health`: Health check endpoint
- `http://host:port/metrics`: Metrics endpoint (optional)

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_stt.py

# Run with coverage
pytest --cov=app tests/
```

## Docker Deployment

```bash
# Build image
docker build -f docker/Dockerfile -t voice-translator .

# Run with docker-compose
docker-compose -f docker/docker-compose.yml up
```

## Performance

- **STT Latency**: ~100-200ms
- **Translation Latency**: ~50-100ms
- **TTS Latency**: ~200-300ms
- **Total End-to-End Latency**: ~500ms (target)

## Project Structure

```
voice-to-voice-translator/
├── app/                    # Application code
│   ├── main.py            # Entry point
│   ├── config/            # Configuration
│   ├── server/            # WebSocket server
│   ├── rooms/             # Room management
│   ├── pipeline/          # STT, Translation, TTS
│   ├── audio/             # Audio processing
│   ├── messaging/         # WebSocket messages
│   ├── security/          # Auth and rate limiting
│   ├── workers/           # Background workers
│   └── utils/             # Utilities
├── models/                # ML models storage
├── scripts/               # Utility scripts
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: <repository-url>/issues
- Documentation: [docs/](docs/)

## Roadmap

- [ ] Add more language pairs
- [ ] Implement GPU acceleration
- [ ] Add speaker diarization
- [ ] Web-based client interface
- [ ] Mobile app support
- [ ] Cloud deployment guides
