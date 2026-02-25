# Latency Strategy

## Overview

This document defines latency strategy for the current Go-first runtime.

Current behavior:

- HTTP endpoints are ingress for clients.
- Translation and TTS HTTP paths route internally through gRPC clients to gRPC handlers in the same Go process.
- STT HTTP paths call the STT worker directly.

## Current Request Paths

### Translation

```text
HTTP /translate or /translate/batch
  -> Go HTTP handler
  -> internal gRPC client (TranslationService)
  -> Go gRPC handler
  -> SarvamTranslator worker
  -> translate_engine daemon
  -> llama-server
  -> response
```

### TTS

```text
HTTP /tts/generate or /translate-tts (TTS stage)
  -> Go HTTP handler
  -> internal gRPC client (TTSService)
  -> Go gRPC handler
  -> SvaraTTS worker
  -> tts_engine daemon (ONNX)
  -> WAV bytes
  -> response
```

`/tts/generate?stream=true` and `/translate-tts?stream=true` relay gRPC `SynthesizeStream` chunks to HTTP.

### STT

```text
HTTP /stt/*
  -> Go HTTP handler
  -> PythonSTTBridge.Transcribe(...)
  -> python -c
  -> STTFactory/VoskEngine
  -> response
```

## Latency Priorities (Highest Impact First)

1. Reduce model/runtime compute time in Translation and TTS daemons.
2. Control queueing and concurrency to avoid tail-latency spikes.
3. Keep request payloads bounded (text/audio size discipline).
4. Use streaming where it improves user-perceived latency.
5. Optimize protocol overhead only after runtime/queue tuning.

## Service-Specific Strategy

### Translation

Primary latency drivers:

- daemon queue wait
- llama inference time
- retries/circuit behavior under failure

Tuning knobs:

- `SARVAM_DAEMON_WORKERS`
- `SARVAM_DAEMON_QUEUE_SIZE`
- `SARVAM_THREADS`
- `SARVAM_MAX_TOKENS`
- `SARVAM_MAX_INPUT_CHARS`
- `SARVAM_GPU_LAYERS` (when GPU is stable)

Guidance:

- Keep input text bounded.
- Start with conservative workers, then increase while tracking p95/p99.
- Avoid overprovisioning workers beyond CPU budget.

### TTS

Primary latency drivers:

- ONNX synthesis time
- queue depth under concurrency
- audio payload size

Tuning knobs:

- `SVARA_TTS_DAEMON_WORKERS`
- `SVARA_TTS_DAEMON_QUEUE_SIZE`
- `SVARA_TTS_ONNX_THREADS`
- `SVARA_TTS_MAX_INPUT_CHARS`
- `SVARA_TTS_TIMEOUT_SECONDS`
- `SVARA_TTS_ONNX_SAMPLE_RATE`

Guidance:

- Use `?stream=true` for real-time UX.
- Keep text shorter in interactive/rolling contexts.
- Tune ONNX threads to hardware; avoid thread oversubscription.

### STT

Primary latency drivers:

- per-request Python process spawn (`python -c`)
- Vosk decode/model path

Guidance:

- Keep chunk and payload sizes reasonable.
- Use warm-start for expected languages.
- For major improvements, move to persistent STT runtime architecture.

## SLO Targets (Suggested)

- Translation `/translate`: p50 <= 300 ms, p95 <= 900 ms
- Translation `/translate/batch` (3 short texts): p50 <= 700 ms, p95 <= 1800 ms
- TTS `/tts/generate` (short text): p50 <= 450 ms, p95 <= 1400 ms
- Translate+TTS `/translate-tts` (short text): p50 <= 900 ms, p95 <= 2500 ms
- STT `/stt/transcribe` (short clip): track separately; expected variance is higher

Adjust by hardware tier and model size.

## Measurement Plan

Collect per-endpoint:

- request count
- success/error rate
- p50/p95/p99 latency
- timeout rate
- queue-related errors

Collect per worker/daemon:

- queue depth
- active workers
- timeout count
- restart/crash count

Run load tests in phases:

1. Baseline: single-user, warm runtime.
2. Moderate concurrency: expected production average.
3. Stress: overload to observe tail and failure behavior.

## Rollout Strategy

1. Establish baseline metrics for current traffic profile.
2. Apply one tuning change at a time.
3. Compare p95/p99 and error rate against baseline.
4. Keep rollback-ready env presets for worker/thread/queue configs.

## Expected Outcomes

- Internal gRPC routing provides consistency and enables HTTP stream relay from gRPC streaming methods.
- Main latency gains still come from runtime and queue tuning, not protocol changes alone.
- Translation/TTS improvements are typically small-to-moderate per protocol change, larger with daemon/model tuning.
