# Go Server Guide

## Overview

This document explains the Go server that runs the current platform.

The server provides:

- HTTP APIs
- WebSocket endpoint and room routing
- gRPC services
- Shared worker orchestration (STT/Translation/TTS)
- Unified startup, warm-start, and runtime health checks

## Architecture

### Current Server Topology
```text
+----------------------------------------------+
| go_server/main.go                            |
|                                              |
|  +----------------------+                    |
|  | HTTP Handlers        |                    |
|  +----------------------+                    |
|                                              |
|  +----------------------+                    |
|  | WebSocket Server     |                    |
|  | + room manager       |                    |
|  +----------------------+                    |
|                                              |
|  +----------------------+                    |
|  | gRPC Server          |                    |
|  +----------------------+                    |
|                                              |
|  +----------------------+                    |
|  | Shared Workers       |                    |
|  | STT / Translation /  |                    |
|  | TTS                  |                    |
|  +----------------------+                    |
+----------------------------------------------+
```

### Request Execution Model

```text
HTTP/WS/gRPC request
        |
        v
 Go handler validation
        |
        v
 Shared worker call (STT / Translation / TTS)
        |
        v
 Runtime engine process (Python bridge / C++ daemon)
        |
        v
 Response shaping (JSON / audio / gRPC protobuf)
```

## Related Files

- `AI_Pipeline/go_server/main.go`
- `AI_Pipeline/go_server/server/websocket_server.go`
- `AI_Pipeline/go_server/server/connection_manager.go`
- `AI_Pipeline/go_server/server/heartbeat.go`
- `AI_Pipeline/go_server/server/registry.go`
- `AI_Pipeline/app/rooms/manager.go`
- `AI_Pipeline/app/rooms/room.go`
- `AI_Pipeline/app/messaging/router.go`
- `AI_Pipeline/app/config/settings.go`

## Startup Sequence

1. Load config and logging.
2. Initialize scanner, room manager, and workers.
3. Register WS router.
4. Run warm-start for STT/Translation/TTS.
5. Start gRPC server.
6. Start HTTP server.

Technical behavior:

- gRPC and HTTP/WS share the same worker instances.
- Worker cleanup is done with deferred `Close()` calls for translation/TTS.
- Warm-start mode supports:
  - full translation warm-up
  - common-pairs warm-up
  - STT/TTS preload language sets

## Endpoint Surface

HTTP:

- `/health`, `/stats`, `/config`
- `/languages/supported`, `/languages/pairs`
- `/translate`, `/translate/batch`
- `/tts/generate`, `/translate-tts`
- `/stt/transcribe`, `/stt/transcribe-file`, `/stt/transcribe-batch`

WebSocket:

- `/ws`

gRPC:

- Starts with the Go server.
- Port from `GRPC_PORT`

## Runtime Stats and Health

### `/health` (HTTP)

Returns process-level status and live server counters:

- `status`
- `connections`
- `rooms`
- `total_users`

### `/stats` (HTTP)

Returns structured runtime snapshot:

- `server.version`, `server.environment`
- `connections.total`, `connections.active`
- `rooms.total`, `rooms.active`
- `workers.translation.total`, `workers.translation.busy`, `workers.translation.queue_size`
- `workers.tts.total`, `workers.tts.busy`, `workers.tts.queue_size`

Note:

- Current `busy`/`queue_size` values are placeholder counters in the Go server response shape.
- Real worker internals currently expose health and timeout behavior rather than detailed queue telemetry.

### gRPC `HealthCheck`

gRPC health probes runtime paths, not static language lists:

- STT worker health probe
- Translation worker health probe
- TTS worker health probe

Possible status values:

- `ok`
- `degraded`
- `unhealthy`

## Technical Configuration Defaults (from implementation)

Server/network:

- `HOST=0.0.0.0`
- `PORT=8000`
- `WORKERS=4`
- `WS_PING_INTERVAL=30`
- `WS_PING_TIMEOUT=10`

Limits:

- `MAX_CONNECTIONS=100`
- `MAX_CONNECTIONS_PER_IP=10`
- `MAX_USERS_PER_ROOM=10`
- `MAX_MESSAGE_SIZE=10485760`
- `IDLE_TIMEOUT=300`
- `ROOM_TIMEOUT=3600`

Rate controls:

- `MAX_MESSAGES_PER_SECOND=10`
- `MAX_REQUESTS_PER_MINUTE=100`
- `RATE_LIMIT_PER_MINUTE=60`

Pipeline workers:

- `TRANSLATION_WORKERS=4`
- `TTS_WORKERS=2`
- `WORKER_THREADS=2`
- `QUEUE_SIZE=100`

## Operational Key Points

1. Workers are shared across HTTP, WS, and gRPC paths.
2. Warm-start is configurable per component.
3. Translate+TTS chunk mode uses bounded rolling text context.
4. CORS, limits, and room constraints are env-driven.
5. gRPC can run side-by-side with HTTP/WS on the same process for phased migration.
6. Translation worker includes retry/backoff/circuit-breaker controls.

## Implementation Notes

- WebSocket upgrade endpoint: `/ws`
- HTTP handlers enforce method checks and return structured `detail` errors.
- `/translate-tts` supports:
  - `full_sentence`
  - `chunk` with bounded context window keyed by `stream_id`
- gRPC handlers perform explicit request/language validation before worker calls.
