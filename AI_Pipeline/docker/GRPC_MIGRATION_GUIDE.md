# gRPC Microservices Migration Guide

## Overview

This guide explains how to migrate from the monolithic architecture to a microservices architecture using gRPC for internal communication.

## Architecture Comparison

### Before (Monolith)
```
┌─────────────────────────────────────┐
│     voice-translator-app            │
│  ┌──────────────────────────────┐   │
│  │  WebSocket Server            │   │
│  └──────────┬───────────────────┘   │
│             │                        │
│  ┌──────────▼───────────────────┐   │
│  │  Pipeline Manager            │   │
│  │  ├── STT (Vosk)              │   │
│  │  ├── Translation (Argos)     │   │
│  │  └── TTS (Coqui)             │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

### After (Microservices)
```
┌──────────────┐                ┌────────────────┐
│   Gateway    │                │  STT Service   │
│  (WebSocket) │────gRPC───────▶│    (Vosk)      │
│              │                └────────────────┘
│              │                ┌────────────────┐
│              │────gRPC───────▶│ Translation    │
│              │                │    (Argos)     │
│              │                └────────────────┘
│              │                ┌────────────────┐
│              │────gRPC───────▶│  TTS Service   │
│              │                │    (Coqui)     │
└──────────────┘                └────────────────┘
```

## Benefits

### 1. **Independent Scaling**
- Scale STT service separately (CPU-intensive Vosk processing)
- Scale TTS service separately (GPU-intensive Coqui synthesis)
- Scale Translation service separately (lighter Argos processing)

### 2. **Better Resource Utilization**
- Assign different CPU/memory limits per service
- Use GPU only for TTS service (if available)
- Isolate memory-hungry models

### 3. **Faster Development & Deployment**
- Deploy STT updates without touching TTS
- Test services independently
- Easier debugging and monitoring

### 4. **Fault Isolation**
- STT crash doesn't kill TTS
- Services can restart independently
- Better error handling and recovery

### 5. **Performance**
- gRPC is 30-50% faster than HTTP/JSON for internal communication
- Protocol Buffers are 3-10x faster than JSON serialization
- HTTP/2 multiplexing reduces connection overhead
- Bidirectional streaming for audio pipelines

## Prerequisites

### 1. Install gRPC Tools
```bash
# Python
pip install grpcio grpcio-tools grpcio-health-checking

# For health probes (in Dockerfiles)
wget https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.19/grpc_health_probe-linux-amd64
chmod +x grpc_health_probe-linux-amd64
mv grpc_health_probe-linux-amd64 /usr/local/bin/grpc_health_probe
```

### 2. Generate Python Code from Proto
```bash
cd voice-to-voice-translator
python -m grpc_tools.protoc \
  -I./proto \
  --python_out=./app/grpc_generated \
  --grpc_python_out=./app/grpc_generated \
  ./proto/voice_translator.proto
```

## Implementation Steps

### Step 1: Create Service Dockerfiles

#### `Dockerfile.gateway`
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt grpcio grpcio-tools

# Copy application
COPY app/ ./app/
COPY proto/ ./proto/

# Generate gRPC code
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./app/grpc_generated \
    --grpc_python_out=./app/grpc_generated \
    ./proto/voice_translator.proto

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
  CMD curl -f http://localhost:7860/health || exit 1

CMD ["python", "-m", "app.gateway.main"]
```

#### `Dockerfile.stt`
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt grpcio grpcio-tools grpcio-health-checking

# Install grpc_health_probe
RUN wget -qO/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.19/grpc_health_probe-linux-amd64 && \
    chmod +x /bin/grpc_health_probe

# Copy application
COPY app/ ./app/
COPY proto/ ./proto/

# Generate gRPC code
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./app/grpc_generated \
    --grpc_python_out=./app/grpc_generated \
    ./proto/voice_translator.proto

CMD ["python", "-m", "app.services.stt_service"]
```

#### `Dockerfile.translation`
```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt grpcio grpcio-tools grpcio-health-checking

# Install grpc_health_probe
RUN wget -qO/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.19/grpc_health_probe-linux-amd64 && \
    chmod +x /bin/grpc_health_probe

# Copy application
COPY app/ ./app/
COPY proto/ ./proto/

# Generate gRPC code
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./app/grpc_generated \
    --grpc_python_out=./app/grpc_generated \
    ./proto/voice_translator.proto

CMD ["python", "-m", "app.services.translation_service"]
```

#### `Dockerfile.tts`
```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt grpcio grpcio-tools grpcio-health-checking

# Install grpc_health_probe
RUN wget -qO/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.19/grpc_health_probe-linux-amd64 && \
    chmod +x /bin/grpc_health_probe

# Copy application
COPY app/ ./app/
COPY proto/ ./proto/

# Generate gRPC code
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./app/grpc_generated \
    --grpc_python_out=./app/grpc_generated \
    ./proto/voice_translator.proto

CMD ["python", "-m", "app.services.tts_service"]
```

### Step 2: Update requirements.txt
```txt
# Add gRPC dependencies
grpcio==1.60.0
grpcio-tools==1.60.0
grpcio-health-checking==1.60.0
protobuf==4.25.1
```

### Step 3: Deployment

#### Development/Testing (Same VM)
```bash
# Build and start all services
docker-compose up --build

# Services communicate on internal network
# Gateway: http://localhost:7860
# STT: stt-service:50051 (internal only)
# Translation: translation-service:50052 (internal only)
# TTS: tts-service:50053 (internal only)
```

#### Production (Separate VMs - Optional)
```bash
# On VM 1 (STT)
docker run -d \
  --name stt-service \
  -p 50051:50051 \
  voice-translator-stt

# On VM 2 (Translation)
docker run -d \
  --name translation-service \
  -p 50052:50052 \
  voice-translator-translation

# On VM 3 (TTS)
docker run -d \
  --name tts-service \
  -p 50053:50053 \
  voice-translator-tts

# On VM 4 (Gateway)
docker run -d \
  --name gateway \
  -p 7860:7860 \
  -e STT_SERVICE_URL=vm1-ip:50051 \
  -e TRANSLATION_SERVICE_URL=vm2-ip:50052 \
  -e TTS_SERVICE_URL=vm3-ip:50053 \
  voice-translator-gateway
```

## Service Implementation Examples

### STT Service (app/services/stt_service.py)
```python
import grpc
from concurrent import futures
from grpc_health.v1 import health_pb2, health_pb2_grpc
from app.grpc_generated import voice_translator_pb2, voice_translator_pb2_grpc
from app.pipeline.stt import STTFactory

class STTServiceImpl(voice_translator_pb2_grpc.STTServiceServicer):
    def __init__(self):
        self.engines = {}
    
    def RecognizeStream(self, request_iterator, context):
        """Stream audio and return streaming recognition results."""
        recognizer = None
        
        for audio_chunk in request_iterator:
            # Get or create engine for language
            if audio_chunk.language not in self.engines:
                self.engines[audio_chunk.language] = STTFactory.get_engine(audio_chunk.language)
            
            engine = self.engines[audio_chunk.language]
            
            # Create recognizer for this stream
            if recognizer is None:
                recognizer = engine.create_recognizer()
            
            # Process audio
            result = engine.recognize(audio_chunk.audio_data, recognizer)
            
            # Yield result
            yield voice_translator_pb2.RecognitionResult(
                text=result.get("text", ""),
                is_partial=not audio_chunk.is_final,
                confidence=result.get("confidence", 0.0),
                language=audio_chunk.language,
                user_id=audio_chunk.user_id
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    voice_translator_pb2_grpc.add_STTServiceServicer_to_server(STTServiceImpl(), server)
    
    # Add health checking
    health_servicer = health_pb2_grpc.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
```

### Gateway Client (app/gateway/grpc_client.py)
```python
import grpc
from app.grpc_generated import voice_translator_pb2, voice_translator_pb2_grpc

class GRPCClient:
    def __init__(self, stt_url, translation_url, tts_url):
        # Create channels
        self.stt_channel = grpc.insecure_channel(stt_url)
        self.translation_channel = grpc.insecure_channel(translation_url)
        self.tts_channel = grpc.insecure_channel(tts_url)
        
        # Create stubs
        self.stt_stub = voice_translator_pb2_grpc.STTServiceStub(self.stt_channel)
        self.translation_stub = voice_translator_pb2_grpc.TranslationServiceStub(self.translation_channel)
        self.tts_stub = voice_translator_pb2_grpc.TTSServiceStub(self.tts_channel)
    
    async def process_audio_stream(self, audio_chunks):
        """Process streaming audio through the pipeline."""
        # STT: Audio -> Text
        stt_results = self.stt_stub.RecognizeStream(audio_chunks)
        
        # Translation: Text -> Translated Text
        for stt_result in stt_results:
            translation_request = voice_translator_pb2.TranslationRequest(
                text=stt_result.text,
                source_lang=stt_result.language,
                target_lang="hi"  # Example
            )
            translation_result = self.translation_stub.Translate(translation_request)
            
            # TTS: Translated Text -> Audio
            tts_request = voice_translator_pb2.TTSRequest(
                text=translation_result.translated_text,
                language=translation_result.target_lang
            )
            tts_result = self.tts_stub.Synthesize(tts_request)
            
            yield tts_result.audio_data
```

## Monitoring & Debugging

### Check Service Health
```bash
# Via docker
docker ps

# Via grpc_health_probe
grpc_health_probe -addr=stt-service:50051
grpc_health_probe -addr=translation-service:50052
grpc_health_probe -addr=tts-service:50053

# Via docker-compose
docker-compose ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f stt-service
docker-compose logs -f gateway
```

### Performance Testing
```bash
# Test latency between services
docker exec gateway ping stt-service
docker exec gateway ping translation-service
docker exec gateway ping tts-service

# Should be < 1ms on same VM
```

## Rollback to Monolith

If you need to rollback, uncomment the monolith service in `docker-compose.yml`:

```bash
# Stop microservices
docker-compose down

# Edit docker-compose.yml - comment microservices, uncomment monolith

# Start monolith
docker-compose up -d voice-translator-monolith
```

## Performance Comparison

| Metric | Monolith | Microservices (Same VM) | Microservices (Separate VMs) |
|--------|----------|-------------------------|------------------------------|
| Network overhead | 0ms | < 1ms (internal) | 1-5ms (LAN) |
| Memory usage | High (all models) | Lower per service | Lower per service |
| Deployment time | Slow (all models) | Fast (per service) | Fast (per service) |
| Scalability | Vertical only | Horizontal + Vertical | Full horizontal |
| Fault tolerance | Low | Medium | High |

## Next Steps

1. **Phase 1**: Test on same VM with docker-compose
2. **Phase 2**: Add monitoring (Prometheus/Grafana)
3. **Phase 3**: Implement load balancing for services
4. **Phase 4**: Move to separate VMs if needed
5. **Phase 5**: Consider Kubernetes for auto-scaling

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose logs service-name

# Check if port is in use
netstat -tulpn | grep 50051

# Rebuild
docker-compose build --no-cache service-name
```

### gRPC connection errors
```bash
# Verify network
docker network inspect voice-translator-network

# Test connectivity
docker exec gateway ping stt-service

# Check firewall (if separate VMs)
telnet vm-ip 50051
```

### Models not loading
```bash
# Verify volume
docker volume inspect voice-models

# Check model-downloader ran
docker-compose logs model-downloader

# Manually run downloader
docker-compose up model-downloader
```
