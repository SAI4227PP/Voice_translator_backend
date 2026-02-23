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
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------
# Python deps + spaCy model
# -------------------------------
FROM base AS python-deps
WORKDIR /app

# Upgrade pip first (cached separately)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy and install requirements (separate layer for better caching)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Validate and cleanup (separate layer)
RUN python -m spacy validate && \
    find /usr/local/lib/python3.11 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11 -type f -name "*.pyc" -delete

# Verify spaCy model installation
RUN python -c "import spacy; nlp = spacy.load('xx_sent_ud_sm'); print('spaCy model verified:', nlp.meta['name'])"

# -------------------------------
# Production runtime
# -------------------------------
FROM base AS production
WORKDIR /app

# Copy Python deps + spaCy model
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Runtime user & dirs (create BEFORE copying app code for better caching)
RUN mkdir -p logs data models /tmp /app/.local && \
    groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    chmod -R 755 /usr/local/lib/python3.11/site-packages

# Copy app code (after user creation to cache better)
COPY docs/ ./docs/
COPY scripts/ ./scripts/
COPY app/ ./app/

# Set ownership for app files
RUN chown -R appuser:appuser /app /tmp

# -------------------------------
# Runtime environment
# -------------------------------
ENV HOST=0.0.0.0 \
    PORT=7860 \
    WORKERS=1 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production \
    DEBUG=False \
    ARGOS_PACKAGES_DIR=/app/models/translate/argos-packages \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    XDG_CACHE_HOME=/tmp \
    HOME=/app \
    SPACY_NO_DOWNLOADS=1 \
    PIP_NO_INPUT=1 \
    PIP_USER=0

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
