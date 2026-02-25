# API Guide

## Overview

This document describes the current API surface of the Go-based Voice Translator backend:

- HTTP/JSON endpoints
- WebSocket endpoint
- gRPC services

Default local base URLs:

- HTTP: `http://localhost:8000`
- WebSocket: `ws://localhost:8000/ws`
- gRPC: `localhost:50051`

## HTTP API

### Health and Metadata

#### `GET /`
Service metadata.

Example response:
```json
{
  "service": "AI_Pipeline",
  "version": "1.0.0",
  "status": "running"
}
```

#### `GET /health`
Basic process and room health.

Example response:
```json
{
  "status": "healthy",
  "connections": 3,
  "rooms": 1,
  "total_users": 2
}
```

#### `GET /stats`
Runtime snapshot (server, rooms, connections, worker totals).

#### `GET /config`
Resolved runtime configuration and discovered languages/models.

#### `GET /languages/supported`
Returns language maps for `stt`, `translation`, and `tts`.

#### `GET /languages/pairs`
Returns supported translation pairs.

Example response:
```json
{
  "pairs": [
    { "from": "en", "to": "hi", "name": "English -> Hindi" }
  ],
  "count": 1
}
```

### Translation

#### `POST /translate`
Translate one text.

Request:
```json
{
  "text": "Hello",
  "source_language": "en",
  "target_language": "hi"
}
```

Response:
```json
{
  "original_text": "Hello",
  "translated_text": "namaste",
  "source_language": "en",
  "target_language": "hi",
  "processing_time_ms": 101.31
}
```

#### `POST /translate/batch`
Translate multiple texts in one request.

Request:
```json
{
  "texts": ["Hello", "How are you?"],
  "source_language": "en",
  "target_language": "hi"
}
```

Response shape:
```json
{
  "translations": [
    { "original": "Hello", "translated": "..." },
    { "original": "How are you?", "translated": "..." }
  ],
  "source_language": "en",
  "target_language": "hi",
  "total": 2,
  "processing_time_ms": 180.45
}
```

### Text-to-Speech

#### `POST /tts/generate`
Generate WAV audio from text.

Request:
```json
{
  "text": "Hello",
  "language": "en",
  "format": "wav"
}
```

Response:
- `Content-Type: audio/wav`
- `Content-Disposition: attachment; filename="tts_output.wav"`
- `X-Processing-Time-Ms: <value>`

### Combined Translate + TTS

#### `POST /translate-tts`
Translate and synthesize in one call.

Request:
```json
{
  "text": "Hello",
  "source_language": "en",
  "target_language": "hi",
  "mode": "full_sentence",
  "stream_id": "call-1",
  "format": "wav"
}
```

Rules:
- `format` must be `wav`
- `mode` must be `full_sentence` or `chunk`
- `stream_id` is required when `mode=chunk`

Response:
- `Content-Type: audio/wav`
- `X-Processing-Time-Ms: <value>`
- `X-Pipeline-Mode: full_sentence|chunk`

### Speech-to-Text

#### `POST /stt/transcribe`
Transcribe base64 audio.

Request:
```json
{
  "audio_data": "<base64-audio>",
  "language": "en",
  "sample_rate": 16000,
  "return_confidence": true
}
```

Response:
```json
{
  "text": "hello world",
  "language": "en",
  "confidence": 0.91,
  "processing_time_ms": 89.12
}
```

#### `POST /stt/transcribe-file`
Multipart file transcription.

Form fields:
- `file` (required)
- `language` (optional, default `en`)
- `return_confidence` (`true`/`false`)

Max file size: `10 MB`

#### `POST /stt/transcribe-batch`
Batch transcription from base64 list.

Request:
```json
{
  "audio_files": ["<base64-1>", "<base64-2>"],
  "language": "en",
  "sample_rate": 16000,
  "return_confidence": false
}
```

## WebSocket API

Endpoint:
- `GET /ws` (upgrades to WebSocket)

Message protocol is documented in:
- `AI_Pipeline/docs/websocket-protocol.md`

## gRPC API

Proto file:
- `AI_Pipeline/proto/voice_translator.proto`

Services:
- `STTService`
  - `RecognizeAudio`
  - `RecognizeStream`
  - `HealthCheck`
- `TranslationService`
  - `Translate`
  - `TranslateStream`
  - `GetSupportedLanguages`
  - `HealthCheck`
- `TTSService`
  - `Synthesize`
  - `SynthesizeStream`
  - `GetVoices`
  - `HealthCheck`

Local generation note:
- Go build requires generated files in `AI_Pipeline/go_server/proto/` (`*.pb.go`).
- Use:
  - `AI_Pipeline/scripts/gen_go_proto.sh`
  - `AI_Pipeline/scripts/gen_go_proto.ps1`

## Error Format

### Generic error
```json
{
  "detail": "Translation failed: <error>"
}
```

### Language validation error
```json
{
  "detail": {
    "error": "Target language 'xx' is not supported",
    "available_languages": ["en", "hi"],
    "message": "Check /languages/supported for available languages"
  }
}
```

HTTP status usage:
- `400` invalid request/payload/format
- `405` method not allowed
- `413` file too large
- `422` unsupported language / invalid domain input
- `500` runtime or pipeline failure

## Notes

- JSON key order is not semantically relevant.
- Streaming chunk mode uses bounded rolling context by `stream_id` in the Go server.
- gRPC handlers include request validation and status-code mapping for worker/runtime failures.
