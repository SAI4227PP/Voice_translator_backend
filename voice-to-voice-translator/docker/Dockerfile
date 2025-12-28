# syntax=docker/dockerfile:1.4

# ======================================================
# Voice-to-Voice Translator – Production Image
# - spaCy models installed ONCE at build time
# - NO runtime downloads
# - Non-root execution
# ======================================================

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    COQUI_TOS_AGREED=1 \
    TTS_USE_SIMPLE_MODELS=true

# -------------------------------
# System dependencies
# -------------------------------
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
# Python deps + spaCy model
# -------------------------------
FROM base AS python-deps
WORKDIR /app

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    python -m spacy download xx_sent_ud_sm

# -------------------------------
# Production runtime
# -------------------------------
FROM base AS production
WORKDIR /app

# Copy Python deps + spaCy model
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy app code
COPY docs/ ./docs/
COPY scripts/ ./scripts/
COPY app/ ./app/

# Runtime user & dirs
RUN mkdir -p logs data models /tmp && \
    groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    chown -R appuser:appuser /app /tmp

# -------------------------------
# Runtime environment
# -------------------------------
ENV HOST=0.0.0.0 \
    PORT=7860 \
    WORKERS=1 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production \
    DEBUG=False \
    ARGOS_PACKAGES_DIR=/app/models/argos \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    XDG_CACHE_HOME=/tmp \
    HOME=/tmp \
    SPACY_NO_DOWNLOADS=1

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
