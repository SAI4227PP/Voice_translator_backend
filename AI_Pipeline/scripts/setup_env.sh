#!/bin/bash
# Setup script for Voice-to-Voice Translator

set -e  # Exit on error

echo "================================"
echo "Voice Translator Setup Script"
echo "================================"

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p models/stt/vosk-en
mkdir -p models/stt/vosk-hi
mkdir -p models/translate/argos-packages
mkdir -p models/tts/coqui-models

# Download models
echo "Downloading models..."
python scripts/download_models.py

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env 2>/dev/null || cat > .env << EOF
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=development
DEBUG=True
EOF
    echo ".env file created. Please review and update as needed."
fi

echo ""
echo "================================"
echo "Setup Complete!"
echo "================================"
echo ""
echo "To start the server:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run server: python app/main.py"
echo ""
echo "Or use: ./venv/bin/python app/main.py"
echo ""
