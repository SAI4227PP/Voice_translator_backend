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

## Translation + TTS Migration (HTTP -> gRPC)

Use this when your immediate focus is Translation and TTS only.

### Endpoint Mapping

- HTTP `POST /translate` -> gRPC `TranslationService.Translate`
- HTTP `POST /translate/batch` -> gRPC `TranslationService.TranslateStream` (or repeated `Translate` calls)
- HTTP `POST /tts/generate` -> gRPC `TTSService.Synthesize`
- Real-time playback path -> gRPC `TTSService.SynthesizeStream`
- HTTP `POST /translate-tts` -> client orchestrates:
  1. `TranslationService.Translate`
  2. `TTSService.Synthesize` or `TTSService.SynthesizeStream`

### Recommended Rollout Order

1. Migrate `/translate` clients to `TranslationService.Translate`.
2. Migrate `/tts/generate` clients to `TTSService.Synthesize`.
3. For real-time audio delivery, switch to `TTSService.SynthesizeStream`.
4. Replace `/translate-tts` with client-side orchestration across Translation + TTS gRPC calls.
5. Keep HTTP endpoints as fallback until p95 latency and error rate are stable.

### Expected Impact

- Transport overhead usually improves due to protobuf + binary framing.
- TTS streaming UX improves with `SynthesizeStream` chunk delivery.
- CPU and latency gains are usually small-to-moderate, not dramatic, because synthesis/inference runtime is still the dominant cost.
- Translation/TTS benefit more than current STT path because these workers are already long-lived daemons.

### What Not to Expect

- gRPC alone does not reduce model inference time.
- gRPC alone does not fix queue contention or daemon saturation.
- If p95 remains high, tune daemon worker/thread/queue settings before deeper architecture changes.

## Key Points

1. gRPC is already production-wired in integrated mode.
2. Health checks probe live worker paths, not static language lists.
3. STT stream partials are rolling-buffer best-effort.
4. TTS stream is chunked post-synthesis.
