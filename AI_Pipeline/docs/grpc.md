# gRPC Guide

## Overview

This document explains the current gRPC implementation and migration target.

Current state:

- gRPC server is integrated into the main Go server process.
- gRPC handlers reuse existing STT/Translation/TTS workers.

## Architecture Comparison

### Before (Integrated gRPC)
```text
+-------------------------------------------+
| voice-translator-app                      |
|                                           |
|  +-------------------------------------+  |
|  | Go Server                           |  |
|  | - HTTP + WebSocket                  |  |
|  | - gRPC (same process)               |  |
|  +------------------+------------------+  |
|                     |                     |
|  +------------------v------------------+  |
|  | Shared Workers                      |  |
|  | - STT bridge                        |  |
|  | - Translation daemon worker         |  |
|  | - TTS daemon worker                 |  |
|  +-------------------------------------+  |
+-------------------------------------------+
```

### After (Microservices Target)
```text
+-------------------+        +----------------------+
| Gateway Service   | gRPC   | STT Service          |
| (WS/HTTP ingress) +------->| (Python Vosk bridge) |
+---------+---------+        +----------------------+
          |
          | gRPC
          v
+----------------------+      +----------------------+
| Translation Service  +----->| TTS Service          |
| (Sarvam daemon)      | gRPC | (Svara daemon)       |
+----------------------+      +----------------------+
```

## Related Files

- `AI_Pipeline/proto/voice_translator.proto`
- `AI_Pipeline/go_server/grpcserver/server.go`
- `AI_Pipeline/go_server/main.go`
- `AI_Pipeline/go_server/proto/gen.go`
- `AI_Pipeline/scripts/gen_go_proto.ps1`
- `AI_Pipeline/scripts/gen_go_proto.sh`

## Services

- `STTService`: `RecognizeAudio`, `RecognizeStream`, `HealthCheck`
- `TranslationService`: `Translate`, `TranslateStream`, `GetSupportedLanguages`, `HealthCheck`
- `TTSService`: `Synthesize`, `SynthesizeStream`, `GetVoices`, `HealthCheck`

## Validation and Error Mapping

gRPC layer includes:

- request field validation
- language validation via scanner
- worker error mapping to status codes:
  - `InvalidArgument`
  - `DeadlineExceeded`
  - `Unavailable`
  - `Internal`

## Build Prerequisites

Local Go build requires generated proto files:

- `go_server/proto/voice_translator.pb.go`
- `go_server/proto/voice_translator_grpc.pb.go`

Generate:

Windows:
```powershell
.\scripts\gen_go_proto.ps1
```

Linux/macOS:
```bash
./scripts/gen_go_proto.sh
```

## Key Points

1. gRPC is already production-wired in integrated mode.
2. Health checks probe live worker paths, not static language lists.
3. STT stream partials are rolling-buffer best-effort.
4. TTS stream is chunked post-synthesis.
