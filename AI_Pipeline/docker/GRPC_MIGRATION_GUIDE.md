# gRPC Microservices Migration Guide

## Overview

This guide describes migration from the current integrated runtime to a service-split gRPC architecture.

Current implementation in this repo:

- Go server is the main entrypoint (`go_server/main.go`)
- gRPC server is integrated in the same process (`go_server/grpcserver/server.go`)
- STT uses Python bridge (`app/workers/stt.go`)
- Translation uses Sarvam C++ daemon (`app/workers/translation.go` + `app/pipeline/translate/translate_engine.cpp`)
- TTS uses Svara C++ daemon (`app/workers/tts.go` + `app/pipeline/tts/tts_engine.cpp`)

## Architecture Comparison

### Before (Integrated Monolith)
```text
+-------------------------------------------+
| voice-translator-app                      |
|                                           |
|  +-------------------------------------+  |
|  | Go API Server                       |  |
|  | - HTTP + WebSocket                  |  |
|  | - Optional gRPC                     |  |
|  +------------------+------------------+  |
|                     |                     |
|  +------------------v------------------+  |
|  | Worker Layer                        |  |
|  | - STT bridge (Python Vosk)          |  |
|  | - Translation worker (Sarvam)       |  |
|  | - TTS worker (Svara)                |  |
|  +-------------------------------------+  |
+-------------------------------------------+
```

### After (Microservices Target)
```text
+----------------------+      gRPC      +------------------------+
| Gateway Service      +--------------->| STT Service            |
| (HTTP/WS ingress)    |                | (Python Vosk bridge)   |
+----------+-----------+                +------------------------+
           |
           | gRPC
           v
+------------------------+      gRPC      +------------------------+
| Translation Service    +--------------->| TTS Service            |
| (Sarvam daemon worker) |                | (Svara daemon worker)  |
+------------------------+                +------------------------+
```

## Benefits

1. Independent scaling
- Scale STT, Translation, and TTS independently.

2. Better resource isolation
- Assign CPU/memory differently per service.
- Isolate high-memory model processes.

3. Fault isolation
- Service crash impact is localized.

4. Deployment flexibility
- Roll out STT/Translation/TTS changes separately.

5. Clear ownership boundaries
- API gateway and model runtimes can evolve independently.

## What Already Exists

Implemented now:

- Proto contract: `proto/voice_translator.proto`
- gRPC server implementation: `go_server/grpcserver/server.go`
- gRPC startup wiring from main server: `go_server/main.go`
- Docker support for gRPC env and port in current app container

Not yet split by default:

- Separate STT/Translation/TTS service binaries/containers
- Dedicated gateway-only service that calls external gRPC runtimes

## Prerequisites

1. Go + protoc toolchain for local development

- Go 1.22+
- `protoc`
- `protoc-gen-go`
- `protoc-gen-go-grpc`

2. Proto generation

Windows:
```powershell
.\scripts\gen_go_proto.ps1
```

Linux/macOS:
```bash
./scripts/gen_go_proto.sh
```

Required generated files:

- `go_server/proto/voice_translator.pb.go`
- `go_server/proto/voice_translator_grpc.pb.go`

## Migration Plan (Recommended)

### Phase 1: Keep integrated server, harden gRPC

- Keep single Go process.
- Use gRPC clients against the integrated server.
- Validate request/response compatibility and health behavior.

### Phase 2: Extract Translation and TTS first

- Create `translation-service` binary using `SarvamTranslator` worker.
- Create `tts-service` binary using `SvaraTTS` worker.
- Keep gateway in current Go server.

### Phase 3: Extract STT service

- Create `stt-service` binary around `PythonSTTBridge`.
- Move stream handling ownership to STT service.

### Phase 4: Gateway-only mode

- Gateway exposes WS/HTTP.
- Gateway calls STT/Translation/TTS via gRPC stubs.

## Service Split Mapping

### Gateway service

Responsibilities:

- Client auth/session (if enabled)
- WS room and routing
- HTTP ingress
- gRPC downstream fan-out

Reuse from:

- `go_server/main.go` (handlers)
- `go_server/server/*`
- `app/rooms/*`
- `app/messaging/*`

### STT service

Responsibilities:

- `RecognizeAudio`
- `RecognizeStream`
- STT health probe

Reuse from:

- `app/workers/stt.go`
- STT parts of `go_server/grpcserver/server.go`

### Translation service

Responsibilities:

- `Translate`
- `TranslateStream`
- `GetSupportedLanguages`

Reuse from:

- `app/workers/translation.go`
- Translation parts of `go_server/grpcserver/server.go`

### TTS service

Responsibilities:

- `Synthesize`
- `SynthesizeStream`
- `GetVoices`

Reuse from:

- `app/workers/tts.go`
- TTS parts of `go_server/grpcserver/server.go`

## Deployment Notes

### Current (single container)

- Build with `docker/Dockerfile`
- Run with `docker/docker-compose.yml`
- Exposes HTTP and optional gRPC from one app container

### Target (multi-container)

Suggested services:

- `gateway`
- `stt-service`
- `translation-service`
- `tts-service`

Use internal docker network and expose only gateway externally.

## Health and Observability

Use:

- HTTP health for gateway process
- gRPC `HealthCheck` for STT/Translation/TTS service probes
- container logs per service

Minimum telemetry to track:

- request latency per service
- queue depth/timeouts
- failure rates and circuit-breaker trips

## Rollback Strategy

- Keep integrated runtime deployment manifest available.
- If split deployment fails, route traffic back to integrated app container.
- Rollback should be only a deployment switch; no proto contract change.

## Risks and Constraints

- Local build fails without generated proto files.
- STT streaming currently uses rolling-buffer partials (not persistent decoder state).
- TTS streaming is chunked post-synthesis, not incremental generation.
- Model/runtime startup latency can affect first-request SLO if warm-start is disabled.

## Quick Validation Checklist

1. Proto generation works locally.
2. gRPC endpoints respond from integrated server.
3. Translation and TTS daemon health probes pass.
4. WS pipeline still functions with gRPC enabled.
5. End-to-end latency remains within target after split.
