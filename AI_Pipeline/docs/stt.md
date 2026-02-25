# STT Component Guide

## Overview

This document explains the STT implementation used in the current Go-first pipeline.

The STT path provides:

- HTTP + gRPC speech transcription entrypoints
- WebSocket-compatible chunk handling through shared server pipeline
- Runtime bridge from Go to Python Vosk
- Warm-start and runtime health probing
- Language-specific Vosk model resolution from config

## Architecture

### Current STT Topology
```text
+-------------------------------------------+
| Go server (HTTP/WS/gRPC handlers)         |
+----------------------+--------------------+
                       |
                       | audio payloads
                       v
+-------------------------------------------+
| PythonSTTBridge (Go worker)               |
| app/workers/stt.go                        |
+----------------------+--------------------+
                       |
                       | python -c bridge call
                       v
+-------------------------------------------+
| STTFactory + VoskEngine (Python)          |
| app/pipeline/stt/*                        |
+----------------------+--------------------+
                       |
                       v
+-------------------------------------------+
| text + confidence                          |
+-------------------------------------------+
```

### Request Execution Model

```text
audio payload (base64/file/chunk)
            |
            v
Go handler validation (method + language + payload)
            |
            v
PythonSTTBridge.Transcribe(...)
            |
            v
inline python runtime -> STTFactory -> recognizer/finalize
            |
            v
JSON parse in Go -> HTTP/gRPC response
```

## Model and Runtime Used

The current STT backend is **Vosk** (Python runtime).

Model loading path:

- `STTFactory.get_engine(language)` chooses engine type from `STT_ENGINE` (default `vosk`)
- `settings.get_vosk_model_path(language)` resolves model directory
- `VoskEngine(model_path, sample_rate)` loads a `vosk.Model`

Default model-related config:

- `STT_ENGINE=vosk`
- `VOSK_MODEL_BASE_PATH=models/stt`
- language-specific paths from settings (`VOSK_MODEL_PATH_EN`, `VOSK_MODEL_PATH_HI`, etc.)
- `AUDIO_SAMPLE_RATE=16000`

Important implementation behavior:

- `PythonSTTBridge.Transcribe` runs `python -c ...` for each call.
- Inside that Python process, `STTFactory` can cache engine instances.
- Because each bridge call starts a new process, cache reuse is limited per invocation.

## Related Files

- `AI_Pipeline/app/workers/stt.go`
- `AI_Pipeline/app/pipeline/stt/stt_factory.py`
- `AI_Pipeline/app/pipeline/stt/vosk_engine.py`
- `AI_Pipeline/go_server/main.go`
- `AI_Pipeline/go_server/grpcserver/server.go`
- `AI_Pipeline/app/config/settings.go`

## API Surface

### HTTP

- `POST /stt/transcribe`
- `POST /stt/transcribe-file`
- `POST /stt/transcribe-batch`

### gRPC

- `STTService.RecognizeAudio`
- `STTService.RecognizeStream`
- `STTService.HealthCheck`

Request format notes:

- HTTP `/stt/transcribe` and `/stt/transcribe-batch` expect base64 audio.
- `/stt/transcribe-file` accepts multipart upload (`file`).
- gRPC audio is raw bytes (`AudioRequest.audio_data`, `AudioChunk.audio_data`).

## Runtime Stats and Health

### HTTP visibility

STT participates in shared server observability:

- `/health` process counters (`connections`, `rooms`, `total_users`)
- `/stats` shared worker metadata section

### gRPC health

STT liveness is probed via runtime path:

- `PythonSTTBridge.HealthCheck("en")`

Status is aggregated as:

- `ok`
- `degraded`
- `unhealthy`

Health is runtime-backed:

- Bridge executes Python import + `STTFactory.get_engine(language)`.
- Failures reflect actual runtime/model issues (missing model, missing Vosk, import errors).

## Streaming Behavior

`RecognizeStream` currently:

- appends incoming chunk bytes into rolling buffer
- emits best-effort partial text for non-final chunks
- emits final transcription for `is_final=true`

Important note:

- This is rolling-buffer transcription, not persistent incremental decoder state.
- Each partial step still calls bridge transcription on accumulated bytes.

## Warm Start and Configuration

Warm-start hooks:

- `PythonSTTBridge.WarmUp(languages)`
- called from `warmStart()` in `go_server/main.go`

Key env:

- `STT_ENGINE=vosk`
- `STT_ENABLE_WARM_START=true`
- `STT_PRELOAD_LANGUAGES=en,hi`
- `VOSK_MODEL_BASE_PATH=models/stt`
- `AUDIO_SAMPLE_RATE=16000`
- `AUDIO_CHUNK_SIZE=4096`

Latency-relevant knobs:

- `STT_PRELOAD_LANGUAGES`: reduce first-request cold path per language
- `AUDIO_SAMPLE_RATE`: higher rates increase payload size and CPU cost
- incoming chunk size and chunk cadence: directly affect partial result frequency

## Latency Strategy (Implementation-Driven)

Observed STT latency stack:

1. Go request validation and payload decode (base64/file/chunk)
2. Python process spawn (`python -c`) per bridge invocation
3. Vosk model load/engine creation in Python path
4. Recognizer run + finalize
5. JSON serialization/parsing and response write

Practical latency guidance:

- Keep audio chunks in the 20-50 ms range for streaming UX.
- Avoid very large one-shot payloads when partial results are needed.
- Use warm-start for expected languages (`STT_PRELOAD_LANGUAGES`).
- Keep sample rate consistent with model expectations (typically 16 kHz PCM16).
- Prefer persistent streaming architecture in future if true incremental low-latency STT is required.

## Error Handling

- Python import/model failures bubble up through bridge errors.
- gRPC maps bridge errors to status codes (`InvalidArgument`, `DeadlineExceeded`, `Internal`, etc.).
- HTTP handlers return structured `detail` responses.

## Operational Key Points

1. STT is process-bridge based; per-request Python invocation overhead is real.
2. gRPC and HTTP STT paths share same worker behavior.
3. Handler-level language validation prevents unsupported calls.
4. Model quality and size directly impact latency and recognition quality.
5. Current bridge is simple and robust, but not optimized for ultra-low-latency incremental STT.

## Constraints

- No true incremental STT decoder streaming state in current Go gRPC flow.
- Bridge architecture trades simplicity/integration for extra process overhead.
- Large/poor-quality audio can degrade latency and confidence reliability.
