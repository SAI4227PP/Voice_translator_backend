# syntax=docker/dockerfile:1.4

# ======================================================
# Voice-to-Voice Translator – Optimized Production Image
# - NO model downloads at build time
# - NO secrets in image
# - Models loaded via runtime volume
# ======================================================

# -------------------------------
# Stage 1: Base image
# -------------------------------
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    COQUI_TOS_AGREED=1 \
    TTS_USE_SIMPLE_MODELS=true

# System dependencies (cached)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    portaudio19-dev \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------
# Stage 2: Python dependencies
# -------------------------------
FROM base AS python-deps

WORKDIR /app

# Copy requirements first (best caching)
COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    python -m spacy download xx_sent_ud_sm


# -------------------------------
# Stage 3: Production runtime
# -------------------------------
FROM base AS production

WORKDIR /app

# Copy Python dependencies
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy application code only
COPY requirements.txt README.md GETTING_STARTED.md API_DOCUMENTATION.md ./
COPY docs/ ./docs/
COPY scripts/ ./scripts/
COPY app/ ./app/

# Runtime directories (models come from volume)
RUN mkdir -p logs data models && \
    groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    chown -R appuser:appuser /app

# Runtime environment
ENV HOST=0.0.0.0 \
    PORT=7860 \
    WORKERS=1 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production \
    DEBUG=False \
    ARGOS_PACKAGES_DIR=/app/models/argos \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    HOME=/tmp \
    SPACY_HOME=/tmp \
    XDG_CACHE_HOME=/tmp

# Cache dirs
RUN mkdir -p /tmp/numba_cache /tmp/.cache /tmp/spacy && \
    chmod -R 777 /tmp

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
