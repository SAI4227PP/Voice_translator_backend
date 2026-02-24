# syntax=docker/dockerfile:1.4

# ======================================================
# Voice-to-Voice Translator - Production Image
# - Multi-stage build to keep final image slim
# - Python deps installed at build time
# - No runtime downloads
# - Non-root execution
# ======================================================

# -------------------------------
# Runtime base (no compilers)
# -------------------------------
FROM python:3.11-slim AS runtime-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    libgcc-s1 \
    libgomp1 \
    libportaudio2 \
    libsndfile1 \
    ffmpeg \
    libcurl4 \
    curl \
    ca-certificates \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------
# Build base (toolchains)
# -------------------------------
FROM python:3.11-slim AS build-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    CCACHE_DIR=/root/.cache/ccache

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    ccache \
    cmake \
    make \
    portaudio19-dev \
    libsndfile1 \
    libsndfile1-dev \
    libopenblas-dev \
    ffmpeg \
    libcurl4-openssl-dev \
    curl \
    wget \
    git \
    ca-certificates \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------
# Python dependencies
# -------------------------------
FROM build-base AS python-deps
WORKDIR /app

COPY requirements.runtime.txt .

RUN --mount=type=cache,id=vtb-pip-cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.runtime.txt

RUN find /usr/local/lib/python3.11 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11 -type f -name "*.pyc" -delete

# -------------------------------
# llama.cpp build
# -------------------------------
FROM build-base AS llama-build
WORKDIR /work

RUN --mount=type=cache,target=/root/.cache/ccache \
    git clone --depth 1 https://github.com/ggerganov/llama.cpp /work/llama.cpp && \
    CC="ccache gcc" CXX="ccache g++" cmake -S /work/llama.cpp -B /work/llama.cpp/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_BLAS=ON \
      -DGGML_BLAS_VENDOR=OpenBLAS && \
    cmake --build /work/llama.cpp/build -j"$(nproc)" && \
    mkdir -p /work/llama-runtime/bin && \
    if [ -d /work/llama.cpp/build/bin ]; then \
      cp -a /work/llama.cpp/build/bin/. /work/llama-runtime/bin/; \
    elif [ -d /work/llama.cpp/bin ]; then \
      cp -a /work/llama.cpp/bin/. /work/llama-runtime/bin/; \
    else \
      echo "ERROR: llama.cpp binaries not found in bin/ or build/bin/" && exit 1; \
    fi

# -------------------------------
# Sarvam model download + GGUF conversion
# -------------------------------
FROM build-base AS model-build
WORKDIR /work

ARG SARVAM_HF_MODEL_ID=sarvamai/sarvam-1
ARG SVARA_TTS_GGUF_HF_REPO=mradermacher/svara-tts-v1-GGUF
ARG SVARA_TTS_GGUF_FILE=svara-tts-v1.Q5_K_M.gguf
ARG HF_TOKEN

COPY --from=llama-build /work/llama.cpp /work/llama.cpp

RUN --mount=type=cache,id=vtb-pip-cache,target=/root/.cache/pip \
    pip install huggingface_hub==0.36.2 && \
    if [ -f /work/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt ]; then \
      pip install -r /work/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt; \
    fi

RUN --mount=type=cache,id=vtb-pip-cache,target=/root/.cache/pip \
    pip install --upgrade --force-reinstall \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple \
      torch==2.6.0 && \
    pip install --upgrade --force-reinstall \
      transformers==4.55.4 \
      numpy==1.24.3

RUN python3 - <<'PY'
import torch, transformers, numpy
print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("numpy", numpy.__version__)
assert transformers.__version__ == "4.55.4", f"unexpected transformers version: {transformers.__version__}"
assert torch.__version__.startswith("2.6.0"), f"unexpected torch version: {torch.__version__}"
assert numpy.__version__ == "1.24.3", f"unexpected numpy version: {numpy.__version__}"
PY

RUN --mount=type=cache,id=vtb-hf-cache,target=/root/.cache/huggingface \
    --mount=type=cache,id=vtb-model-cache,target=/work/model-cache \
    mkdir -p /work/model-cache/sarvam-1 && \
    if [ -f /work/model-cache/sarvam-1/config.json ]; then \
      echo "Using cached Sarvam HF snapshot"; \
    else \
      python3 -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='${SARVAM_HF_MODEL_ID}', local_dir='/work/model-cache/sarvam-1', token='${HF_TOKEN}' if '${HF_TOKEN}' else None, local_dir_use_symlinks=False)"; \
    fi && \
    rm -rf /work/sarvam-1 && cp -a /work/model-cache/sarvam-1 /work/sarvam-1

RUN --mount=type=cache,id=vtb-model-cache,target=/work/model-cache \
    set -eu; \
    mkdir -p /work/llm-models /work/model-cache && \
    if [ -f /work/model-cache/sarvam-1-q4.gguf ] && [ -f /work/model-cache/sarvam-1.gguf ]; then \
      echo "Using cached GGUF artifacts"; \
      cp /work/model-cache/sarvam-1.gguf /work/llm-models/sarvam-1.gguf; \
      cp /work/model-cache/sarvam-1-q4.gguf /work/llm-models/sarvam-1-q4.gguf; \
    else \
      if [ -f /work/llama.cpp/convert-hf-to-gguf.py ]; then \
        python3 /work/llama.cpp/convert-hf-to-gguf.py /work/sarvam-1 --outfile /work/llm-models/sarvam-1-f16.gguf --outtype f16; \
      elif [ -f /work/llama.cpp/convert_hf_to_gguf.py ]; then \
        python3 /work/llama.cpp/convert_hf_to_gguf.py /work/sarvam-1 --outfile /work/llm-models/sarvam-1-f16.gguf --outtype f16; \
      elif [ -f /work/llama.cpp/convert.py ]; then \
        python3 /work/llama.cpp/convert.py /work/sarvam-1 --outfile /work/llm-models/sarvam-1-f16.gguf --outtype f16; \
      else \
        echo "ERROR: could not find llama.cpp HF->GGUF conversion script" && exit 1; \
      fi; \
      [ -f /work/llm-models/sarvam-1-f16.gguf ]; \
      cp /work/llm-models/sarvam-1-f16.gguf /work/llm-models/sarvam-1.gguf; \
      if [ -x /work/llama.cpp/build/bin/llama-quantize ]; then \
        /work/llama.cpp/build/bin/llama-quantize /work/llm-models/sarvam-1-f16.gguf /work/llm-models/sarvam-1-q4.gguf Q4_K_M; \
      elif [ -x /work/llama.cpp/bin/llama-quantize ]; then \
        /work/llama.cpp/bin/llama-quantize /work/llm-models/sarvam-1-f16.gguf /work/llm-models/sarvam-1-q4.gguf Q4_K_M; \
      elif [ -x /work/llama.cpp/build/bin/quantize ]; then \
        /work/llama.cpp/build/bin/quantize /work/llm-models/sarvam-1-f16.gguf /work/llm-models/sarvam-1-q4.gguf Q4_K_M; \
      elif [ -x /work/llama.cpp/bin/quantize ]; then \
        /work/llama.cpp/bin/quantize /work/llm-models/sarvam-1-f16.gguf /work/llm-models/sarvam-1-q4.gguf Q4_K_M; \
      else \
        echo "ERROR: llama-quantize/quantize binary not found; cannot create q4 model" && exit 1; \
      fi; \
      [ -f /work/llm-models/sarvam-1-q4.gguf ]; \
      cp /work/llm-models/sarvam-1.gguf /work/model-cache/sarvam-1.gguf; \
      cp /work/llm-models/sarvam-1-q4.gguf /work/model-cache/sarvam-1-q4.gguf; \
    fi

RUN --mount=type=cache,id=vtb-hf-cache,target=/root/.cache/huggingface \
    --mount=type=cache,id=vtb-model-cache,target=/work/model-cache \
    set -eu; \
    mkdir -p /work/llm-models /work/model-cache/svara-gguf && \
    if [ -f "/work/model-cache/${SVARA_TTS_GGUF_FILE}" ]; then \
      echo "Using cached Svara GGUF artifact"; \
    else \
      python3 -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='${SVARA_TTS_GGUF_HF_REPO}', local_dir='/work/model-cache/svara-gguf', allow_patterns=['${SVARA_TTS_GGUF_FILE}'], token='${HF_TOKEN}' if '${HF_TOKEN}' else None, local_dir_use_symlinks=False)" && \
      cp "/work/model-cache/svara-gguf/${SVARA_TTS_GGUF_FILE}" "/work/model-cache/${SVARA_TTS_GGUF_FILE}"; \
    fi && \
    cp "/work/model-cache/${SVARA_TTS_GGUF_FILE}" "/work/llm-models/${SVARA_TTS_GGUF_FILE}"

RUN --mount=type=cache,id=vtb-model-cache,target=/work/model-cache \
    set -eu; \
    if [ ! -f "/work/llm-models/${SVARA_TTS_GGUF_FILE}" ]; then \
      echo "ERROR: expected local Svara GGUF model not found: /work/llm-models/${SVARA_TTS_GGUF_FILE}" && exit 1; \
    fi; \
    echo "Using local Svara GGUF model: /work/llm-models/${SVARA_TTS_GGUF_FILE}"

# -------------------------------
# C++ engine builds
# -------------------------------
FROM build-base AS cpp-build
WORKDIR /app

COPY app/ ./app/

RUN --mount=type=cache,target=/root/.cache/ccache \
    cmake -S /app/app/pipeline/translate -B /app/app/pipeline/translate/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && \
    cmake --build /app/app/pipeline/translate/build --target translate_engine -j"$(nproc)" && \
    cmake -S /app/app/pipeline/tts -B /app/app/pipeline/tts/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && \
    cmake --build /app/app/pipeline/tts/build --target tts_engine -j"$(nproc)"

# -------------------------------
# Go websocket server build
# -------------------------------
FROM golang:1.22-bookworm AS go-build
WORKDIR /go-src

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2 && \
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1

COPY go_server/ ./go_server/
COPY app/config/ ./app/config/
COPY app/messaging/ ./app/messaging/
COPY app/rooms/ ./app/rooms/
COPY app/utils/ ./app/utils/
COPY app/workers/ ./app/workers/
COPY proto/ ./proto/

WORKDIR /go-src/go_server
RUN mkdir -p /go-src/go_server/proto && \
    cd /go-src/proto && \
    /usr/bin/protoc -I . \
    --plugin=protoc-gen-go=/go/bin/protoc-gen-go \
    --plugin=protoc-gen-go-grpc=/go/bin/protoc-gen-go-grpc \
    --go_out=/go-src/go_server/proto \
    --go_opt=paths=source_relative \
    --go-grpc_out=/go-src/go_server/proto \
    --go-grpc_opt=paths=source_relative \
    voice_translator.proto

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go mod tidy && \
    go mod download

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /out/voice-translator-go-server ./main.go

# -------------------------------
# Final production image
# -------------------------------
FROM runtime-base AS production
WORKDIR /app

COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

COPY docs/ ./docs/
COPY scripts/ ./scripts/
COPY app/ ./app/

# Copy only llama runtime binaries/scripts required at runtime
RUN mkdir -p /app/llama.cpp/bin
COPY --from=llama-build /work/llama-runtime/bin/ /app/llama.cpp/bin/

# Copy prebuilt model artifacts only
COPY --from=model-build /work/llm-models/ /app/llm-models/

# Copy compiled C++ daemons only
COPY --from=cpp-build /app/app/pipeline/translate/translate_engine /app/app/pipeline/translate/translate_engine
COPY --from=cpp-build /app/app/pipeline/tts/tts_engine /app/app/pipeline/tts/tts_engine
COPY --from=go-build /out/voice-translator-go-server /app/go_server/voice-translator-go-server

RUN mkdir -p logs data models /tmp /app/.local && \
    groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    chmod -R 755 /usr/local/lib/python3.11/site-packages && \
    chown -R appuser:appuser /app /tmp

ENV HOST=0.0.0.0 \
    PORT=7860 \
    WORKERS=1 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production \
    DEBUG=False \
    TRANSLATION_ENGINE=sarvam \
    SARVAM_MODEL_PATH=/app/llm-models/sarvam-1-q4.gguf \
    SARVAM_CPP_BINARY_PATH=/app/app/pipeline/translate/translate_engine \
    SARVAM_DAEMON_WORKERS=2 \
    SARVAM_DAEMON_QUEUE_SIZE=256 \
    SARVAM_MAX_INPUT_CHARS=4000 \
    SARVAM_GPU_LAYERS=0 \
    LLAMA_SERVER_PORT=8089 \
    TRANSLATION_RETRY_COUNT=2 \
    TRANSLATION_RETRY_BACKOFF_MS=250 \
    TRANSLATION_CIRCUIT_BREAKER_THRESHOLD=5 \
    TRANSLATION_CIRCUIT_BREAKER_RESET_SECONDS=30 \
    LLAMA_CPP_PATH=/app/llama.cpp \
    LLAMA_CLI_PATH=/app/llama.cpp/bin/llama-cli \
    TTS_ENGINE=svara \
    SVARA_TTS_CPP_BINARY_PATH=/app/app/pipeline/tts/tts_engine \
    SVARA_TTS_MODEL_ID=/app/llm-models/svara-tts-v1.Q5_K_M.gguf \
    SVARA_TTS_ONNX_MODEL_PATH= \
    SVARA_TTS_TOKENIZER_ID=kenpath/svara-tts-v1 \
    TTS_DAEMON_WORKERS=2 \
    SVARA_TTS_API_BASE_URL= \
    SVARA_TTS_API_KEY= \
    SVARA_TTS_TIMEOUT_SECONDS=90 \
    SVARA_TTS_MAX_INPUT_CHARS=1200 \
    SVARA_TTS_DEFAULT_VOICE=anushka \
    SVARA_TTS_DAEMON_WORKERS=2 \
    SVARA_TTS_DAEMON_QUEUE_SIZE=128 \
    GO_SERVER_BINARY_PATH=/app/go_server/voice-translator-go-server \
    GRPC_PORT=50051 \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    XDG_CACHE_HOME=/tmp \
    HOME=/app \
    PIP_NO_INPUT=1 \
    PIP_USER=0

USER appuser

EXPOSE 7860 50051

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["/app/go_server/voice-translator-go-server"]
