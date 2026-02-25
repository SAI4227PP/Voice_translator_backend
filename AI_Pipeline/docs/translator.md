# Translator Component Guide

## Overview

This document explains the translation implementation used in the current Go-first pipeline.

- Ingress: HTTP / gRPC handlers in Go
- Runtime: Sarvam C++ daemon managed by Go worker
- Purpose: Translate text across supported language pairs
- Backend engine: `llama-server` with Sarvam GGUF model

## Architecture

### Current Translation Flow
```text
+---------------------------+
| Go Handler                |
| /translate or gRPC        |
+-------------+-------------+
              |
              | text + source/target
              v
+---------------------------+
| SarvamTranslator          |
| app/workers/translation.go|
+-------------+-------------+
              |
              | JSON over stdin/stdout
              v
+---------------------------+
| translate_engine daemon   |
| app/pipeline/translate/*  |
+-------------+-------------+
              |
              | HTTP stream completion
              v
+---------------------------+
| llama-server runtime      |
+---------------------------+
```

### Request Execution Model

```text
text request
    |
    v
Go handler validation (text/source/target)
    |
    v
SarvamTranslator.Translate(...)
    |
    v
translate_engine daemon request (JSON stdin/stdout)
    |
    v
llama-server /completion (stream=true)
    |
    v
translated_text -> response
```

## Model and Runtime Used

### Primary Model

- Model path: `SARVAM_MODEL_PATH`
- Default configured model: `/app/llm-models/sarvam-1-q4.gguf`
- Runtime binary: `SARVAM_CPP_BINARY_PATH` (`translate_engine`)

### Inference Runtime

- `translate_engine` launches `llama-server` from `LLAMA_CPP_PATH`
- Uses local `http://127.0.0.1:<LLAMA_SERVER_PORT>/completion`
- Translation prompt format: `<source2target>{text}`
- Streaming completion enabled (`stream=true`) and aggregated into final text

### Supported Languages

- Translation engine supports 23 language codes:
  `en, as, bn, brx, doi, gu, hi, kn, ks, kok, mai, ml, mni, mr, ne, or, pa, sa, sat, sd, ta, te, ur`

## Related Files

- `AI_Pipeline/app/workers/translation.go`
- `AI_Pipeline/app/workers/settings.go`
- `AI_Pipeline/app/pipeline/translate/translate_engine.cpp`
- `AI_Pipeline/go_server/main.go`
- `AI_Pipeline/go_server/grpcserver/server.go`
- `AI_Pipeline/app/config/settings.go`

## API Integration

### HTTP

- `POST /translate`
- `POST /translate/batch`
- `POST /translate-tts` (translation stage)

### gRPC

- `TranslationService.Translate`
- `TranslationService.TranslateStream`
- `TranslationService.GetSupportedLanguages`
- `TranslationService.HealthCheck`

## Runtime Protocol

Worker -> daemon commands:

- `translate`
- `batch_translate`
- `warm_up`
- `validate`

Payload fields include:

- `id`, `cmd`, `source`, `target`
- `text_b64` (single)
- `batch_b64` (NUL-delimited batch)

Daemon response fields include:

- `status`
- `translated_text`
- `translated_items` (batch path)
- `latency_ms`
- `stderr_snippet`
- `error`

## Reliability

- request timeout
- retry with backoff
- circuit breaker
- daemon queue-bound protection (`queue_full`)

Worker resilience behavior:

- Timeout: `SARVAM_TIMEOUT_SECONDS`
- Retries: `TRANSLATION_RETRY_COUNT`
- Backoff: exponential from `TRANSLATION_RETRY_BACKOFF_MS`
- Circuit opens after `TRANSLATION_CIRCUIT_BREAKER_THRESHOLD` failures
- Circuit reset window: `TRANSLATION_CIRCUIT_BREAKER_RESET_SECONDS`

Key env:

- `SARVAM_CPP_BINARY_PATH`
- `SARVAM_MODEL_PATH`
- `LLAMA_CPP_PATH`
- `SARVAM_TIMEOUT_SECONDS`
- `TRANSLATION_RETRY_COUNT`
- `TRANSLATION_CIRCUIT_BREAKER_*`
- `TRANSLATION_ENABLE_WARM_START`
- `TRANSLATION_COMMON_PAIRS`

Additional latency/perf env:

- `SARVAM_MAX_TOKENS`
- `SARVAM_CONTEXT_SIZE`
- `SARVAM_THREADS`
- `SARVAM_GPU_LAYERS`
- `SARVAM_DAEMON_WORKERS`
- `SARVAM_DAEMON_QUEUE_SIZE`
- `SARVAM_MAX_INPUT_CHARS`
- `LLAMA_SERVER_PORT`

## Latency Strategy (Implementation-Driven)

Translation latency is mainly driven by:

1. Go request validation + worker dispatch
2. Daemon queue wait (`SARVAM_DAEMON_QUEUE_SIZE`, load dependent)
3. `llama-server` inference time (dominant)
4. Worker response decode and API response write

Implementation optimizations already in code:

- Input hard cap by chars (`SARVAM_MAX_INPUT_CHARS`)
- Tail windowing before inference (word/char-bounded context)
- Adaptive `n_predict` by input size
- Pair-based KV slot reuse (`id_slot`) up to 512 slots
- Background warm-up of common pairs

Practical tuning guidance:

- For low latency, keep `SARVAM_MAX_TOKENS` conservative.
- Increase `SARVAM_THREADS` up to available CPU core budget.
- Tune `SARVAM_DAEMON_WORKERS` for concurrency; too high can reduce per-request performance.
- Enable non-zero `SARVAM_GPU_LAYERS` only when GPU is available and stable.

## Warm Start

Warm-start options:

- Full warm-up: `TRANSLATION_WARM_START_MODE=all`
- Common pairs warm-up: `TRANSLATION_WARM_START_MODE=common`
- Pair list via `TRANSLATION_COMMON_PAIRS` (e.g., `en-hi,hi-en,en-bn,bn-en`)

Note:
- Engine also performs internal background warm-up for predefined pairs to prime KV cache paths.

## Key Points

1. Translation is process-isolated via C++ daemon.
2. Go worker owns lifecycle, request correlation, and resilience.
3. Warm-up supports all or configured common pairs.
4. Input text is bounded/truncated for latency and stability.
5. gRPC and HTTP use the same translator worker and daemon instance.
