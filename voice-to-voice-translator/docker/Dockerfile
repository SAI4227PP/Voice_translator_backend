# Multi-stage Dockerfile for Voice-to-Voice Translator
# Optimized for production deployment with all models

# Stage 1: Base image with system dependencies
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    portaudio19-dev \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    wget \
    curl \
    git \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Stage 2: Python dependencies
FROM base as python-deps

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 3: Download models
FROM python-deps as model-downloader

WORKDIR /app

# Create model directories
RUN mkdir -p models/stt models/translate models/tts

# Copy model download script
COPY scripts/download_models.py scripts/

# Download all language models (this may take a while)
# Set a flag to skip interactive prompts
ENV DOWNLOAD_MODELS=1

# Download models with error handling
RUN python scripts/download_models.py || \
    echo "Warning: Some models failed to download. They will be downloaded on first use."

# Stage 4: Final production image
FROM base as production

# Set working directory
WORKDIR /app

# Copy Python dependencies from python-deps stage
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy downloaded models from model-downloader stage
COPY --from=model-downloader /app/models /app/models

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY docs/ ./docs/
COPY .env.example .env
COPY requirements.txt .
COPY README.md .
COPY GETTING_STARTED.md .
COPY API_DOCUMENTATION.md .

# Create necessary directories
RUN mkdir -p logs data && \
    chmod -R 755 /app && \
    # Create non-root user for security
    groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set default environment variables
ENV HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=4 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production \
    DEBUG=False

# Run application with uvicorn for production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "info"]
