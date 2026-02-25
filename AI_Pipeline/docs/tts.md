# TTS Component Guide

## Overview

This document explains the TTS implementation used in the current Go-first pipeline.

The TTS path provides:

- HTTP and gRPC text-to-speech endpoints
- Shared Go worker lifecycle for daemon process management
- WAV response generation with metadata-aware handling
- Chunked gRPC stream output for low-latency delivery
- Local ONNX runtime only (no HTTP TTS fallback)

## Architecture

### Current TTS Topology
```text
+-------------------------------------------+
| Go server (HTTP/gRPC handlers)            |
+----------------------+--------------------+
                       |
                       | text + language
                       v
+-------------------------------------------+
| SvaraTTS worker (Go)                       |
| app/workers/tts.go                         |
+----------------------+--------------------+
                       |
                       | JSON over stdin/stdout
                       v
+-------------------------------------------+
| tts_engine daemon (C++)                    |
| app/pipeline/tts/tts_engine.cpp            |
+----------------------+--------------------+
                       |
                       v
+-------------------------------------------+
| WAV bytes (audio_b64 -> decoded in Go)     |
+-------------------------------------------+
```

### Request Execution Model

```text
text request
    |
    v
Go handler validation (text/language)
    |
    v
SvaraTTS.Synthesize(...)
    |
    v
daemon command -> synthesize
    |
    v
audio_b64 result -> decode -> response
```

## Model and Runtime Used

The current implementation uses **Svara TTS local ONNX runtime only**.

- Required model path: `SVARA_TTS_ONNX_MODEL_PATH`
- Expected model file: `models/tts/svara/svara_tts.onnx` (local/dev) or `/app/tts-models/svara_tts.onnx` (Docker)
- C++ daemon uses ONNX Runtime directly (`TTS_ENGINE_ENABLE_ONNX` build path)
- Output sample rate: `SVARA_TTS_ONNX_SAMPLE_RATE` (default `24000`)

Enforcement:
- Go worker validates that `SVARA_TTS_ONNX_MODEL_PATH` exists and is a `.onnx` file.
- TTS startup fails fast if local ONNX model is missing.
- HTTP TTS mode via external API is disabled in worker startup path.

## Related Files

- `AI_Pipeline/app/workers/tts.go`
- `AI_Pipeline/app/workers/settings.go`
- `AI_Pipeline/app/pipeline/tts/tts_engine.cpp`
- `AI_Pipeline/app/pipeline/tts/tts_engine.hpp`
- `AI_Pipeline/go_server/main.go`
- `AI_Pipeline/go_server/grpcserver/server.go`
- `AI_Pipeline/app/config/settings.go`

## API Surface

### HTTP

- `POST /tts/generate`
- `POST /translate-tts` (TTS stage)

### gRPC

- `TTSService.Synthesize`
- `TTSService.SynthesizeStream`
- `TTSService.GetVoices`
- `TTSService.HealthCheck`

### gRPC Streaming Chunk Size

`SynthesizeStream` sends fixed-time audio shards:

- Target window: ~50 ms
- Chunk bytes formula: `sample_rate * 2 * 50 / 1000` (PCM16 mono)
- At 16 kHz: `1600` bytes
- At 24 kHz: `2400` bytes

## Runtime Stats and Health

### HTTP visibility

TTS contributes to shared runtime visibility via:

- `/health` process-level counters
- `/stats` worker metadata section

### gRPC health

TTS runtime liveness is probed via:

- `SvaraTTS.HealthCheck()`

Aggregated service status:

- `ok`
- `degraded`
- `unhealthy`

Health is runtime-backed:
- Go gRPC health calls `SvaraTTS.HealthCheck()`
- Worker sends daemon `validate` command
- Status reflects daemon readiness, not just static language metadata

## Streaming and Metadata

### `Synthesize`

- validates request
- invokes worker synthesize
- parses WAV metadata in gRPC path when available
- computes fallback length/sample rate if needed

Sample-rate behavior:
- If WAV header exists, gRPC response uses parsed WAV sample rate and duration.
- If parsing fails, response falls back to request sample rate or `AUDIO_SAMPLE_RATE`.

### `SynthesizeStream`

- synthesizes full audio first
- splits into low-latency chunks (target ~50ms, sample-rate derived)
- sends chunks with final marker

Important note:

- Current streaming is chunked delivery of completed audio, not incremental synthesis generation.

## Worker/Daemon Command Contract

Worker -> daemon fields:

- `id`
- `cmd` (`synthesize`, `warm_up`, `validate`, `shutdown`)
- `language`
- `text_b64`

Daemon -> worker fields:

- `status`
- `audio_b64`
- `latency_ms`
- `error`

## Warm Start and Configuration

Warm-start hooks:

- `SvaraTTS.WarmUp(languages)`
- integrated in `warmStart()` from `go_server/main.go`

Key env:

- `SVARA_TTS_CPP_BINARY_PATH`
- `SVARA_TTS_ONNX_MODEL_PATH`
- `SVARA_TTS_MODEL_ID`
- `SVARA_TTS_TIMEOUT_SECONDS`
- `SVARA_TTS_DAEMON_WORKERS`
- `SVARA_TTS_DAEMON_QUEUE_SIZE`
- `SVARA_TTS_ONNX_SAMPLE_RATE`
- `TTS_ENABLE_WARM_START`
- `TTS_PRELOAD_LANGUAGES`

Latency-critical knobs:

- `SVARA_TTS_DAEMON_WORKERS`: parallel synthesis workers in C++ daemon
- `SVARA_TTS_DAEMON_QUEUE_SIZE`: backpressure queue depth before rejects/timeouts
- `SVARA_TTS_TIMEOUT_SECONDS`: per request timeout
- `SVARA_TTS_MAX_INPUT_CHARS`: caps long inputs and avoids extreme synthesis times
- `SVARA_TTS_ONNX_THREADS`: ONNX CPU parallelism
- `SVARA_TTS_ONNX_SAMPLE_RATE`: output fidelity vs bandwidth/size tradeoff

## Latency Strategy (Implementation-Driven)

Observed latency stack in this TTS path:

1. Go handler validation and request routing
2. Worker request enqueue/write to daemon stdin
3. Daemon synthesis time (dominant component)
4. Base64 decode in Go and response write
5. gRPC stream chunk emission (50 ms shard size)

Practical latency guidance:

- Keep text short in chunk mode (`/translate-tts` with rolling context).
- Increase `SVARA_TTS_DAEMON_WORKERS` for concurrent users, but tune against CPU cores.
- Align client playback buffering with 30-50 ms chunk cadence.
- Ensure sample-rate consistency end-to-end (24k ONNX output vs 16k client expectations).

## Error Handling

- daemon start/validate failures return worker errors
- gRPC maps errors to status codes
- HTTP returns structured `detail` messages

## Operational Key Points

1. TTS runtime is process-isolated from API server.
2. gRPC and HTTP paths share same TTS worker and daemon.
3. Voice exposure depends on scanner metadata with fallback behavior.
4. ONNX local model path is mandatory for runtime startup.
5. `SynthesizeStream` improves playback smoothness, but synthesis is still full-audio first.

## Constraints

- Streamed audio is post-synthesis chunking, not live synthesis stream.
- Runtime latency depends on backend mode and hardware.
- Output metadata accuracy depends on WAV parse success and fallback logic.
