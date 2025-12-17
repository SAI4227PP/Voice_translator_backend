# 🚀 Getting Started - Voice-to-Voice Translator

## Welcome!

You now have a **professional, production-ready voice-to-voice translator backend**! This guide will help you get started quickly.

## 📋 What You Have

### ✅ Complete & Ready to Use
- FastAPI WebSocket server
- Room management system
- User connection handling
- Message routing & protocol
- Heartbeat monitoring
- Configuration management
- Structured logging
- Error handling
- Docker deployment files
- Complete documentation

### 📝 Needs Implementation
- STT (Speech-to-Text) engine
- Translation engine  
- TTS (Text-to-Speech) engine
- Audio processing pipeline
- Security layer (optional)
- Worker pools (optional)

## ⚡ Quick Start (5 Minutes)

### Step 1: Setup Environment

```bash
# Navigate to project
cd voice-to-voice-translator

# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Start the Server

```bash
# Run the server
python app/main.py
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Step 3: Test It!

Open another terminal and run:

```bash
# Test health endpoint
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "connections": 0,
  "rooms": 0,
  "total_users": 0
}
```

## 🧪 Test WebSocket Connection

### Using Python:

```python
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        # Join a room
        await ws.send(json.dumps({
            "type": "join_room",
            "payload": {
                "room_id": "test_room",
                "user_id": "user123",
                "username": "Test User",
                "source_lang": "en",
                "target_lang": "hi"
            }
        }))
        
        # Get response
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(test())
```

Save as `test_client.py` and run:
```bash
python test_client.py
```

### Using Browser Console:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
    console.log('Connected!');
    ws.send(JSON.stringify({
        type: 'join_room',
        payload: {
            room_id: 'browser_test',
            user_id: 'user456',
            username: 'Browser User',
            source_lang: 'en',
            target_lang: 'hi'
        }
    }));
};

ws.onmessage = (event) => {
    console.log('Received:', JSON.parse(event.data));
};
```

## 📚 Project Structure

```
voice-to-voice-translator/
├── app/                    # Application source code
│   ├── main.py            # 👈 START HERE - Application entry point
│   ├── config/            # Settings and logging
│   ├── server/            # WebSocket server & connections
│   ├── rooms/             # Room management
│   ├── messaging/         # Message protocol & routing
│   └── utils/             # Utilities
│
├── docs/                  # 📖 Complete documentation
│   ├── architecture.md    # System design
│   ├── websocket-protocol.md  # Protocol spec
│   ├── latency-strategy.md    # Performance guide
│   └── deployment.md      # Deployment guide
│
├── scripts/               # Utility scripts
│   ├── download_models.py # Model downloader
│   ├── setup_env.sh       # Environment setup
│   └── health_check.py    # Health checker
│
├── docker/                # Docker files
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── tests/                 # Test suite
├── models/                # ML models storage
├── .env                   # Configuration
├── requirements.txt       # Dependencies
├── README.md              # Main documentation
├── PROJECT_STATUS.md      # 📋 Implementation guide
└── IMPLEMENTATION_SUMMARY.md  # 📊 Project summary
```

## 🎯 What Works Right Now

✅ Server starts and accepts WebSocket connections  
✅ Users can join and leave rooms  
✅ Messages are routed correctly  
✅ Heartbeat monitoring keeps connections alive  
✅ Health check endpoint reports status  
✅ Multiple users can be in same room  
✅ Room membership is tracked  
✅ User disconnections are handled gracefully  

## 🔧 Configuration

Edit `.env` file to customize:

```ini
# Server
HOST=0.0.0.0
PORT=8000

# Logging
LOG_LEVEL=INFO

# Audio
AUDIO_SAMPLE_RATE=16000
AUDIO_CHUNK_SIZE=4096

# Rooms
MAX_USERS_PER_ROOM=10
ROOM_TIMEOUT=3600

# And more...
```

## 📖 Key Documentation Files

1. **README.md** - Project overview and features
2. **PROJECT_STATUS.md** - Detailed implementation status with code examples
3. **IMPLEMENTATION_SUMMARY.md** - Complete summary of what's done
4. **docs/websocket-protocol.md** - Complete WebSocket protocol
5. **docs/architecture.md** - System architecture and design

## 🔨 Next Steps

### To Add Full Translation Capability:

1. **Download Models** (when ready):
   ```bash
   python scripts/download_models.py
   ```

2. **Implement Pipeline Components**:
   - `app/pipeline/stt/vosk_engine.py` - Speech recognition
   - `app/pipeline/translate/argos_engine.py` - Translation
   - `app/pipeline/tts/coqui_engine.py` - Speech synthesis
   - `app/pipeline/pipeline_manager.py` - Orchestration

3. **See PROJECT_STATUS.md** for detailed implementation guide with code examples

### To Deploy with Docker:

```bash
# Build and run
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_websocket.py -v

# With coverage
pytest --cov=app tests/
```

## 🔍 Health Check

```bash
# Run comprehensive health check
python scripts/health_check.py
```

This checks:
- Dependencies installed
- Configuration files
- Models present
- Server running

## 🐛 Troubleshooting

### Server won't start
```bash
# Check if port is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # Linux/Mac

# Check dependencies
pip install -r requirements.txt
```

### WebSocket connection fails
```bash
# Verify server is running
curl http://localhost:8000/health

# Check firewall settings
# Ensure port 8000 is open
```

### Import errors
```bash
# Make sure you're in the right directory
cd voice-to-voice-translator

# Activate virtual environment
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

## 📞 API Endpoints

- `GET /` - Root endpoint (service info)
- `GET /health` - Health check
- `WS /ws` - WebSocket endpoint for clients

## 💡 Pro Tips

1. **Use the logs**: Check `logs/app.log` for detailed information
2. **Read the docs**: `docs/` folder has comprehensive guides
3. **Check examples**: `tests/test_websocket.py` has working examples
4. **Monitor performance**: Built-in performance tracking available
5. **Follow the protocol**: See `docs/websocket-protocol.md` for message formats

## 🎓 Learning Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **WebSockets**: https://websockets.readthedocs.io/
- **Vosk**: https://alphacephei.com/vosk/
- **Argos Translate**: https://github.com/argosopentech/argos-translate
- **Coqui TTS**: https://github.com/coqui-ai/TTS

## 📝 Code Quality

The codebase follows:
- ✅ PEP 8 style guide
- ✅ Type hints throughout
- ✅ Comprehensive docstrings
- ✅ Structured logging
- ✅ Error handling best practices

## 🎉 You're Ready!

Your voice translator backend is set up and ready for development. The infrastructure is complete - now you can focus on implementing the ML pipeline components.

**Happy Coding!** 🚀

---

**Need Help?**
- Check PROJECT_STATUS.md for implementation guidance
- Review docs/ for architectural details
- Run health_check.py to verify setup
- See IMPLEMENTATION_SUMMARY.md for complete overview
