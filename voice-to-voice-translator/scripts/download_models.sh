#!/bin/bash
# Download models using Docker container
# This avoids Python version and pip conflicts

set -e

echo "============================================================"
echo "Voice Translator - Model Downloader (Docker)"
echo "============================================================"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Create models directory
MODELS_DIR="/opt/voice-models"
echo ""
echo "📁 Creating models directory: $MODELS_DIR"
sudo mkdir -p "$MODELS_DIR"
sudo chown -R $(id -u):$(id -g) "$MODELS_DIR" 2>/dev/null || true

# Check if image exists
IMAGE_NAME="voice-translator"
if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
    echo ""
    echo "⚠️  Docker image '$IMAGE_NAME' not found"
    echo "Building image first..."
    cd "$(dirname "$0")/../docker"
    docker build -t "$IMAGE_NAME" .
    cd - > /dev/null
fi

echo ""
echo "🚀 Running model downloader in Docker container..."
echo "   Volume: $MODELS_DIR:/app/models"
echo ""

# Run download script in container as root (needed to create directories)
docker run --rm \
    --user root \
    -v "$MODELS_DIR:/app/models" \
    -e ARGOS_PACKAGES_DIR=/app/models/translate/argos-packages \
    "$IMAGE_NAME" \
    python scripts/download_models.py

# Fix ownership of downloaded models
echo ""
echo "🔧 Fixing file permissions..."
sudo chown -R $(id -u):$(id -g) "$MODELS_DIR"

echo ""
echo "============================================================"
echo "✅ Models downloaded successfully!"
echo "============================================================"
echo ""
echo "Models are now in: $MODELS_DIR"
echo ""
echo "You can now start the container:"
echo ""
echo "  docker run -d -p 7860:7860 \\"
echo "    --restart unless-stopped \\"
echo "    --env-file .env \\"
echo "    -v $MODELS_DIR:/app/models \\"
echo "    --name voice-translator \\"
echo "    $IMAGE_NAME"
echo ""
