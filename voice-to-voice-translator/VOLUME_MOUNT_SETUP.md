# Volume Mount Setup Guide

This guide explains how to set up persistent model storage using Docker volumes.

## Quick Start

### 1. Download Models (First Time Only)

Run the download script to populate `/opt/voice-models` directory:

```bash
# Create the directory
sudo mkdir -p /opt/voice-models

# Run download script (as root to write to /opt)
sudo python scripts/download_models.py

# Or run inside a temporary container
docker run --rm \
  -v /opt/voice-models:/app/models \
  voice-translator \
  python scripts/download_models.py
```

### 2. Run Container with Volume Mount

```bash
docker run -d -p 7860:7860 \
  --restart unless-stopped \
  --env-file .env \
  -v /opt/voice-models:/app/models \
  --name voice-translator \
  voice-translator
```

## Directory Structure

The volume mount creates this structure in `/opt/voice-models`:

```
/opt/voice-models/
├── stt/                              # Speech-to-Text models
│   ├── vosk-en/                      # English Vosk model
│   ├── vosk-hi/                      # Hindi Vosk model
│   ├── vosk-te/                      # Telugu Vosk model
│   ├── vosk-gu/                      # Gujarati Vosk model
│   └── vosk-bn/                      # Bengali Vosk model
├── translate/
│   └── argos-packages/               # Argos translation packages
│       ├── translate-en_hi-1_9.argosmodel
│       ├── translate-hi_en-1_9.argosmodel
│       ├── translate-en_bn-1_0.argosmodel
│       └── translate-bn_en-1_0.argosmodel
└── tts/
    └── coqui-models/                 # Coqui TTS cache (auto-populated)
```

## Environment Variables

The container is configured with these defaults:

```bash
# In Dockerfile
ARGOS_PACKAGES_DIR=/app/models/translate/argos-packages
HOME=/app
SPACY_NO_DOWNLOADS=1
```

These ensure:
- ✅ Argos packages load from volume mount
- ✅ spaCy model doesn't re-download
- ✅ TTS cache persists across restarts

## Available Models

### Speech-to-Text (STT)
- **English** (en) - US English
- **Hindi** (hi) - Hindi
- **Telugu** (te) - Telugu  
- **Gujarati** (gu) - Gujarati
- **Bengali** (bn) - Bengali/Indian English

### Translation
- **English ↔ Hindi** (en-hi, hi-en)
- **English ↔ Bengali** (en-bn, bn-en)
- Other pairs use English as bridge: Source → English → Target

### Text-to-Speech (TTS)
Uses Coqui XTTS v2 which supports:
- **Indian Languages**: English, Hindi, Bengali, Telugu, Tamil, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Urdu, Assamese, Odia
- **Other Languages**: Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Czech, Arabic, Chinese, Japanese, Korean, Hungarian

## Docker Commands

### Build Image
```bash
cd voice-to-voice-translator/docker
docker build -t voice-translator .
```

### Run with Volume Mount
```bash
docker run -d -p 7860:7860 \
  --restart unless-stopped \
  --env-file .env \
  -v /opt/voice-models:/app/models \
  --name voice-translator \
  voice-translator
```

### Check Logs
```bash
docker logs -f voice-translator
```

### Stop/Remove Container
```bash
docker stop voice-translator
docker rm voice-translator
```

### Update Models
```bash
# Download new models to volume
docker run --rm \
  -v /opt/voice-models:/app/models \
  voice-translator \
  python scripts/download_models.py

# Restart container to load new models
docker restart voice-translator
```

## Warm Start Configuration

Models are preloaded at startup for zero cold-start latency.

Configure in `.env`:

```bash
# STT Warm Start
STT_ENABLE_WARM_START=True
STT_PRELOAD_LANGUAGES=en,hi,bn,te

# Translation Warm Start
TRANSLATION_ENABLE_WARM_START=True
TRANSLATION_WARM_START_MODE=common
TRANSLATION_COMMON_PAIRS=en-hi,hi-en,en-bn,bn-en

# TTS Warm Start
TTS_ENABLE_WARM_START=True
TTS_PRELOAD_LANGUAGES=en,hi,bn,ta
```

**Modes:**
- `TRANSLATION_WARM_START_MODE=common` - Only preload common pairs (fast)
- `TRANSLATION_WARM_START_MODE=all` - Preload all installed packages (slower, comprehensive)

## Troubleshooting

### Models Not Found

**Issue**: `installed_packages=0` in logs

**Solution**: Run download script to populate `/opt/voice-models`
```bash
sudo python scripts/download_models.py
# Or use temporary container
docker run --rm -v /opt/voice-models:/app/models voice-translator python scripts/download_models.py
```

### spaCy Model Downloads at Runtime

**Issue**: spaCy downloads `xx-sent-ud-sm` every startup

**Solution**: Already fixed in latest Dockerfile with:
- `PIP_USER=0` - Prevents user installation
- `HOME=/app` - Consistent home directory
- Model installed via `requirements.txt`

### Permission Errors

**Issue**: Cannot write to `/opt/voice-models`

**Solution**: Set correct ownership
```bash
sudo chown -R 1000:1000 /opt/voice-models
```

### TTS Models Re-downloading

**Issue**: TTS downloads models on every restart

**Solution**: TTS cache is inside the volume at `/app/models/tts/coqui-models/`. First download is expected, subsequent starts reuse cache.

## Performance Tips

1. **SSD Storage**: Place `/opt/voice-models` on SSD for faster model loading
2. **Memory**: Allocate at least 4GB RAM for concurrent model warm start
3. **Preload Strategy**: Use `common` mode for faster startup, `all` for comprehensive coverage
4. **Disable Warm Start**: Set `*_ENABLE_WARM_START=False` to save memory (cold start on first request)

## Production Checklist

- [ ] Models downloaded to `/opt/voice-models`
- [ ] Volume ownership set (`1000:1000`)
- [ ] `.env` file configured with warm start settings
- [ ] Container running with `--restart unless-stopped`
- [ ] Health check endpoint responding: `http://localhost:7860/health`
- [ ] Logs show warm start completion without downloads

## Example Output

Successful startup logs:
```
INFO:     Initializing spaCy model...
INFO:     ✓ spaCy model loaded: xx_sent_ud_sm
INFO:     Initializing STT models...
INFO:     ✓ Vosk model 'en' loaded
INFO:     ✓ Vosk model 'hi' loaded
INFO:     Initializing translation models...
INFO:     ✓ Using ARGOS_PACKAGES_DIR: /app/models/translate/argos-packages
INFO:     ✓ Found 4 installed packages
INFO:     ✓ Translation model 'en' → 'hi' warmed up
INFO:     ✓ Translation model 'hi' → 'en' warmed up
INFO:     Initializing TTS models...
INFO:     ✓ TTS model loaded for language: en
INFO:     ✓ TTS model loaded for language: hi
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:7860
```

## See Also

- [Docker Deployment Guide](docker/DOCKER_DEPLOYMENT.md)
- [Model Download Script](scripts/download_models.py)
- [Warm Start Documentation](TTS_WARM_START.md)
