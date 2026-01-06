#!/bin/bash
# Alternative: Download models using Python virtual environment
# Use this if you don't want to use Docker

set -e

echo "============================================================"
echo "Voice Translator - Model Downloader (venv)"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv-download"

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate and install dependencies
echo "📥 Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet aiohttp tqdm argostranslate

# Run download script
echo ""
echo "🚀 Downloading models..."
cd "$PROJECT_DIR"
python scripts/download_models.py

# Cleanup
deactivate
echo ""
echo "============================================================"
echo "✅ Models downloaded successfully!"
echo "============================================================"
echo ""
echo "Models are in: $PROJECT_DIR/models"
echo ""
echo "You can now:"
echo "  1. Copy models to /opt/voice-models:"
echo "     sudo cp -r models/* /opt/voice-models/"
echo ""
echo "  2. Run with Docker:"
echo "     docker run -d -p 7860:7860 \\"
echo "       --restart unless-stopped \\"
echo "       -v /opt/voice-models:/app/models \\"
echo "       --name voice-translator \\"
echo "       voice-translator"
echo ""
