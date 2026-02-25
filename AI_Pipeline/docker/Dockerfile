# syntax=docker/dockerfile:1.4
# Note: COMPOSE_BAKE=true is a Docker Compose performance hint, not an error.

# ======================================================
# AI_Pipeline - Production Image
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
    PYTHONOPTIMIZE=2 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,id=vtb-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=vtb-apt-lib,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    libgcc-s1 \
    libgomp1 \
    libgfortran5 \
    libopenblas0-pthread \
    libportaudio2 \
    libsndfile1 \
    ffmpeg \
    libcurl4 \
    curl \
    ca-certificates \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/* && \
    set -eux; \
    for d in /usr/lib/*-linux-gnu/openblas-*; do \
      if [ -f "$d/libopenblas.so.0" ]; then \
        ln -sf "$d/libopenblas.so.0" /usr/lib/x86_64-linux-gnu/libopenblas.so.0; \
        ln -sf "$d/libopenblas.so.0" /usr/lib/libopenblas.so.0; \
        break; \
      fi; \
    done

# -------------------------------
# Build base (toolchains)
# -------------------------------
FROM python:3.11-slim AS build-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONOPTIMIZE=2 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    CCACHE_DIR=/root/.cache/ccache

RUN --mount=type=cache,id=vtb-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=vtb-apt-lib,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    libpython3-dev \
    ccache \
    cmake \
    make \
    tar \
    portaudio19-dev \
    libsndfile1-dev \
    libopenblas-dev \
    libcurl4-openssl-dev \
    curl \
    wget \
    git \
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
# llama.cpp source (pin/ref cache boundary)
# -------------------------------
FROM build-base AS llama-source
WORKDIR /work

ARG LLAMA_CPP_REPO=https://github.com/ggerganov/llama.cpp
ARG LLAMA_CPP_REF=master

RUN --mount=type=cache,id=vtb-git-cache,target=/root/.cache/git \
    git init /work/llama.cpp && \
    cd /work/llama.cpp && \
    git remote add origin "${LLAMA_CPP_REPO}" && \
    git fetch --depth 1 origin "${LLAMA_CPP_REF}" && \
    git checkout --detach FETCH_HEAD

# -------------------------------
# llama.cpp build
# -------------------------------
FROM build-base AS llama-build
WORKDIR /work

COPY --from=llama-source /work/llama.cpp /work/llama.cpp

RUN --mount=type=cache,id=vtb-ccache,target=/root/.cache/ccache \
    CC="ccache gcc" CXX="ccache g++" cmake -S /work/llama.cpp -B /work/llama.cpp/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_BLAS=ON \
      -DGGML_BLAS_VENDOR=OpenBLAS && \
    cmake --build /work/llama.cpp/build -j"$(nproc)" && \
    find /work/llama.cpp/build -type f -executable -exec strip --strip-unneeded {} + 2>/dev/null || true && \
    mkdir -p /work/llama-runtime/bin /work/llama-runtime/lib && \
    if [ -d /work/llama.cpp/build/bin ]; then \
      cp -a /work/llama.cpp/build/bin/. /work/llama-runtime/bin/; \
    elif [ -d /work/llama.cpp/bin ]; then \
      cp -a /work/llama.cpp/bin/. /work/llama-runtime/bin/; \
    else \
      echo "ERROR: llama.cpp binaries not found in bin/ or build/bin/" && exit 1; \
    fi && \
    find /work/llama.cpp/build -type f -name "*.so*" -exec cp -a {} /work/llama-runtime/lib/ \;

# -------------------------------
# Sarvam model download + GGUF conversion
# -------------------------------
FROM build-base AS model-build
WORKDIR /work

ARG SARVAM_HF_MODEL_ID=sarvamai/sarvam-1
ARG SVARA_TTS_HF_MODEL_ID=kenpath/svara-tts-v1
ARG SVARA_TTS_GGUF_FILE=svara-tts-v1.Q5_K_M.gguf
ARG HF_TOKEN

COPY --from=llama-build /work/llama.cpp /work/llama.cpp

RUN --mount=type=cache,id=vtb-pip-cache,target=/root/.cache/pip \
    pip install huggingface_hub==0.36.2 && \
    if [ -f /work/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt ]; then \
      pip install -r /work/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt; \
    fi

RUN --mount=type=cache,id=vtb-pip-cache,target=/root/.cache/pip \
    pip install --upgrade \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple \
      torch==2.6.0 && \
    pip install --upgrade \
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
    rm -rf /work/sarvam-1 && cp -a /work/model-cache/sarvam-1/. /work/sarvam-1/

RUN --mount=type=cache,id=vtb-hf-cache,target=/root/.cache/huggingface \
    --mount=type=cache,id=vtb-model-cache,target=/work/model-cache \
    mkdir -p /work/model-cache/svara-tts-hf && \
    if [ -f /work/model-cache/svara-tts-hf/config.json ]; then \
      echo "Using cached Svara HF snapshot"; \
    else \
      python3 -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='${SVARA_TTS_HF_MODEL_ID}', local_dir='/work/model-cache/svara-tts-hf', token='${HF_TOKEN}' if '${HF_TOKEN}' else None, local_dir_use_symlinks=False)"; \
    fi && \
    rm -rf /work/svara-tts && cp -a /work/model-cache/svara-tts-hf/. /work/svara-tts/

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

RUN --mount=type=cache,id=vtb-model-cache,target=/work/model-cache \
    set -eu; \
    mkdir -p /work/llm-models /work/model-cache && \
    if [ -f "/work/model-cache/${SVARA_TTS_GGUF_FILE}" ]; then \
      echo "Using cached Svara GGUF artifact"; \
      cp "/work/model-cache/${SVARA_TTS_GGUF_FILE}" "/work/llm-models/${SVARA_TTS_GGUF_FILE}"; \
    else \
      # Build FP16 GGUF backbone first, then quantize that backbone artifact.
      # This follows the GGUF flow (Q4/Q5/Q6) and does not imply quantizing
      # non-GGUF custom decoder components.
      if [ -f /work/llama.cpp/convert-hf-to-gguf.py ]; then \
        python3 /work/llama.cpp/convert-hf-to-gguf.py /work/svara-tts --outfile /work/llm-models/svara-tts-v1-backbone-f16.gguf --outtype f16; \
      elif [ -f /work/llama.cpp/convert_hf_to_gguf.py ]; then \
        python3 /work/llama.cpp/convert_hf_to_gguf.py /work/svara-tts --outfile /work/llm-models/svara-tts-v1-backbone-f16.gguf --outtype f16; \
      elif [ -f /work/llama.cpp/convert.py ]; then \
        python3 /work/llama.cpp/convert.py /work/svara-tts --outfile /work/llm-models/svara-tts-v1-backbone-f16.gguf --outtype f16; \
      else \
        echo "ERROR: could not find llama.cpp HF->GGUF conversion script for Svara" && exit 1; \
      fi; \
      [ -f /work/llm-models/svara-tts-v1-backbone-f16.gguf ]; \
      if [ -x /work/llama.cpp/build/bin/llama-quantize ]; then \
        /work/llama.cpp/build/bin/llama-quantize /work/llm-models/svara-tts-v1-backbone-f16.gguf "/work/llm-models/${SVARA_TTS_GGUF_FILE}" Q5_K_M; \
      elif [ -x /work/llama.cpp/bin/llama-quantize ]; then \
        /work/llama.cpp/bin/llama-quantize /work/llm-models/svara-tts-v1-backbone-f16.gguf "/work/llm-models/${SVARA_TTS_GGUF_FILE}" Q5_K_M; \
      elif [ -x /work/llama.cpp/build/bin/quantize ]; then \
        /work/llama.cpp/build/bin/quantize /work/llm-models/svara-tts-v1-backbone-f16.gguf "/work/llm-models/${SVARA_TTS_GGUF_FILE}" Q5_K_M; \
      elif [ -x /work/llama.cpp/bin/quantize ]; then \
        /work/llama.cpp/bin/quantize /work/llm-models/svara-tts-v1-backbone-f16.gguf "/work/llm-models/${SVARA_TTS_GGUF_FILE}" Q5_K_M; \
      else \
        echo "ERROR: llama-quantize/quantize binary not found; cannot create Svara GGUF quantized model" && exit 1; \
      fi; \
      [ -f "/work/llm-models/${SVARA_TTS_GGUF_FILE}" ]; \
      cp "/work/llm-models/${SVARA_TTS_GGUF_FILE}" "/work/model-cache/${SVARA_TTS_GGUF_FILE}"; \
    fi

RUN --mount=type=cache,id=vtb-model-cache,target=/work/model-cache \
    set -eu; \
    if [ ! -f "/work/llm-models/${SVARA_TTS_GGUF_FILE}" ]; then \
      echo "ERROR: expected local Svara GGUF model not found: /work/llm-models/${SVARA_TTS_GGUF_FILE}" && exit 1; \
    fi; \
    echo "Using local Svara GGUF model: /work/llm-models/${SVARA_TTS_GGUF_FILE}"

# -------------------------------
# Model downloader image (standalone setup target)
# -------------------------------
FROM runtime-base AS model-downloader

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN --mount=type=cache,id=vtb-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=vtb-apt-lib,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,id=vtb-pip-cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install aiohttp tqdm

RUN find /usr/local/lib/python3.11 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11 -type f -name "*.pyc" -delete && \
    rm -rf /tmp/*

COPY scripts/download_models.py scripts/download_models.py

RUN mkdir -p models/stt models/tts/svara

# -------------------------------
# C++ engine builds
# -------------------------------
FROM build-base AS cpp-build
WORKDIR /app

COPY app/ ./app/

RUN --mount=type=cache,id=vtb-ccache,target=/root/.cache/ccache \
    cmake -S /app/app/pipeline/translate -B /app/app/pipeline/translate/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && \
    cmake --build /app/app/pipeline/translate/build --target translate_engine -j"$(nproc)" && \
    cmake -S /app/app/pipeline/tts -B /app/app/pipeline/tts/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && \
    cmake --build /app/app/pipeline/tts/build --target tts_engine -j"$(nproc)" && \
    strip --strip-unneeded /app/app/pipeline/translate/translate_engine 2>/dev/null || true && \
    strip --strip-unneeded /app/app/pipeline/tts/tts_engine 2>/dev/null || true

# -------------------------------
# Go websocket server build
# -------------------------------
FROM golang:1.22-bookworm AS go-build
WORKDIR /go-src

RUN --mount=type=cache,id=vtb-go-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=vtb-go-apt-lib,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,id=vtb-go-mod,target=/go/pkg/mod \
    --mount=type=cache,id=vtb-go-build,target=/root/.cache/go-build \
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

RUN --mount=type=cache,id=vtb-go-mod,target=/go/pkg/mod \
    --mount=type=cache,id=vtb-go-build,target=/root/.cache/go-build \
    go mod tidy && \
    go mod download

RUN --mount=type=cache,id=vtb-go-mod,target=/go/pkg/mod \
    --mount=type=cache,id=vtb-go-build,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -trimpath -ldflags="-s -w" -o /out/voice-translator-go-server ./main.go

# -------------------------------
# Final production image
# -------------------------------
FROM runtime-base AS production
WORKDIR /app

COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy only llama runtime binaries/scripts required at runtime
RUN mkdir -p /app/llama.cpp/bin /app/llama.cpp/lib
COPY --from=llama-build /work/llama-runtime/bin/ /app/llama.cpp/bin/
COPY --from=llama-build /work/llama-runtime/lib/ /app/llama.cpp/lib/

# Copy prebuilt model artifacts only
COPY --from=model-build /work/llm-models/ /app/llm-models/

# Copy python runtime app package; then remove Go-only subtrees/artifacts
COPY app/ /app/app/
RUN find /app/app -type f -name "*.go" -delete && \
    find /app/app -type f -name "go.mod" -delete

# Copy compiled daemons and server binaries only
RUN mkdir -p /app/bin
COPY --from=cpp-build /app/app/pipeline/translate/translate_engine /app/bin/translate_engine
COPY --from=cpp-build /app/app/pipeline/tts/tts_engine /app/bin/tts_engine
COPY --from=go-build /out/voice-translator-go-server /app/bin/voice-translator-go-server

RUN mkdir -p logs data models /tmp /app/.local && \
    groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    chmod -R 755 /usr/local/lib/python3.11/site-packages && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app -type f -name "*.pyc" -delete && \
    chown -R appuser:appuser /app /tmp

ENV HOST=0.0.0.0 \
    PORT=7860 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production \
    DEBUG=False \
    TRANSLATION_ENGINE=sarvam \
    SARVAM_MODEL_PATH=/app/llm-models/sarvam-1-q4.gguf \
    SARVAM_CPP_BINARY_PATH=/app/bin/translate_engine \
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
    LLAMA_CLI_PATH=- \
    TTS_ENGINE=svara \
    SVARA_TTS_CPP_BINARY_PATH=/app/bin/tts_engine \
    SVARA_TTS_MODEL_ID=/app/llm-models/svara-tts-v1.Q5_K_M.gguf \
    SVARA_TTS_TIMEOUT_SECONDS=90 \
    SVARA_TTS_MAX_INPUT_CHARS=600 \
    SVARA_TTS_DEFAULT_VOICE=anushka \
    SVARA_TTS_DAEMON_WORKERS=2 \
    SVARA_TTS_DAEMON_QUEUE_SIZE=128 \
    SVARA_TTS_THREADS=2 \
    SVARA_TTS_CONTEXT_SIZE=1024 \
    SVARA_TTS_PIN_WORKERS=false \
    GRPC_PORT=50051 \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    XDG_CACHE_HOME=/tmp \
    LD_LIBRARY_PATH=/app/llama.cpp/lib:/app/llama.cpp/bin:${LD_LIBRARY_PATH} \
    HOME=/app

USER appuser

EXPOSE 7860 50051

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["/app/bin/voice-translator-go-server"]

