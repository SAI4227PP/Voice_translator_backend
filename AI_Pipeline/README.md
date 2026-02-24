# Voice-to-Voice Translator

Real-time voice translation backend with a Go API layer, C++ translation/TTS daemons, Python STT bridge, WebSocket rooms, and gRPC services.

## Current Stack

- API server: Go (`go_server/main.go`)
- WebSocket transport: Go room-based server
- STT: Python Vosk bridge (`app/workers/stt.go`)
- Translation: Sarvam C++ daemon (`app/pipeline/translate/translate_engine.cpp`)
- TTS: Svara C++ daemon (`app/pipeline/tts/tts_engine.cpp`)
- Proto/gRPC: `proto/voice_translator.proto`

## Features

- Low-latency STT -> Translate -> TTS pipeline
- WebSocket room routing for multi-user sessions
- HTTP APIs for STT, translation, TTS, and combined pipeline
- gRPC services for STT, translation, and TTS
- Internal HTTP -> gRPC routing for Translation/TTS paths
- HTTP streaming relay for TTS via `?stream=true`
- Docker build with prebuilt C++ binaries and model artifacts

## Prerequisites (Local Run)

- Go 1.22+
- Python 3.11+
- CMake + C++ toolchain
- `protoc` (for local gRPC code generation)

## Quick Start (Docker Recommended)

```bash
docker compose -f docker/docker-compose.yml up --build
```

Default endpoints:

- HTTP: `http://localhost:7860`
- WebSocket: `ws://localhost:7860/ws`
- gRPC: `localhost:50051`

## Quick Start (Local Development)

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Generate Go proto stubs (required for local Go build):

Windows PowerShell:

```powershell
.\scripts\gen_go_proto.ps1
```

Linux/macOS:

```bash
./scripts/gen_go_proto.sh
```

3. Run Go server:

```bash
cd go_server
go run .
```

## Important Note About gRPC Build

The Go server imports generated files from `go_server/proto`.  
Docker generates them during image build, but local IDE/local `go build` requires you to run the proto generation scripts first.

Generated files:

- `go_server/proto/voice_translator.pb.go`
- `go_server/proto/voice_translator_grpc.pb.go`

## Core Endpoints

- `GET /health`
- `GET /stats`
- `GET /config`
- `GET /languages/supported`
- `GET /languages/pairs`
- `POST /translate`
- `POST /translate/batch`
- `POST /tts/generate`
- `POST /tts/generate?stream=true`
- `POST /translate-tts`
- `POST /translate-tts?stream=true`
- `POST /stt/transcribe`
- `POST /stt/transcribe-file`
- `POST /stt/transcribe-batch`
- `GET /ws` (WebSocket upgrade path)

Pipeline note:

- Translation/TTS HTTP routes use internal gRPC clients and handlers before worker execution.
- STT HTTP routes remain direct worker calls.

## gRPC

Proto file:

- `proto/voice_translator.proto`

Services:

- `STTService`
- `TranslationService`
- `TTSService`

Environment flags:

- `GRPC_PORT` (default `50051`)

## Project Structure

```text
AI_Pipeline/
  app/
    config/        # Go config package
    messaging/     # Go websocket message router/protocol
    pipeline/      # C++ engines and Python runtime modules
    rooms/         # Go room manager
    utils/         # Go utilities (scanner/logger/errors/timers)
    workers/       # Go workers (STT bridge, translation, TTS)
  go_server/
    grpcserver/    # gRPC service implementation
    server/        # WebSocket server internals
    proto/         # Generated Go protobuf/grpc files
    main.go        # Go server entrypoint
  proto/
    voice_translator.proto
  docker/
    Dockerfile
    docker-compose.yml
  scripts/
    gen_go_proto.ps1
    gen_go_proto.sh
```

## Docs

- API guide: `docs/api.md`
- Architecture: `docs/architecture.md`
- Go server: `docs/go-server.md`
- gRPC guide: `docs/grpc.md`
- Latency strategy: `docs/latency-strategy.md`
- STT component: `docs/stt.md`
- Translation component: `docs/translator.md`
- TTS component: `docs/tts.md`
- API examples: `Voice_Translator_API.postman_collection.json`
