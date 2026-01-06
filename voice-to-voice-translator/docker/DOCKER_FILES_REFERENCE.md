# Docker Files Reference Guide

Quick reference for understanding what each Docker file contains and its purpose.

---

## 📁 File Structure

```
docker/
├── Dockerfile                      # Main application image
├── Dockerfile.downloader           # Model downloader image
├── docker-compose.yml              # Production setup (with model downloader)
├── docker-compose.local.yml        # Development setup (local models)
├── docker-compose.backup           # Backup of previous config
├── docker-compose.yml.backup       # Another backup
├── DOCKER_DEPLOYMENT.md            # Deployment guide
├── DOCKER_MODEL_SETUP.md           # Model setup troubleshooting
├── DOCKER_FILES_REFERENCE.md       # This file
└── GRPC_MIGRATION_GUIDE.md         # gRPC migration notes
```

---

## 📋 File Contents

### **Dockerfile** (Main Application)
**Purpose:** Builds the production image for the voice translator application

**Contains:**
- ✅ Base image: `python:3.11-slim`
- ✅ System dependencies: `build-essential`, `portaudio19-dev`, `libsndfile1`, `ffmpeg`
- ✅ Python packages from `requirements.txt`
- ✅ spaCy model: `xx_sent_ud_sm` (pre-installed at build time)
- ✅ Application code: `app/`, `docs/`, `scripts/`
- ✅ Runtime user: `appuser` (UID 1000, non-root)
- ✅ Exposed port: `7860`
- ✅ Healthcheck: `curl http://localhost:7860/health`

**Environment Variables Set:**
```dockerfile
HOST=0.0.0.0
PORT=7860
WORKERS=1
ENVIRONMENT=production
ARGOS_PACKAGES_DIR=/app/models/translate/argos-packages
COQUI_TOS_AGREED=1
TTS_USE_SIMPLE_MODELS=true
SPACY_NO_DOWNLOADS=1
```

**Key Features:**
- Multi-stage build (base → python-deps → production)
- spaCy model verified at build time
- Optimized layer caching
- Non-root execution for security

---

### **Dockerfile.downloader** (Model Downloader)
**Purpose:** Downloads all required AI models to a Docker volume

**Contains:**
- ✅ Base image: `python:3.11-slim`
- ✅ System dependencies: `unzip`, `curl`
- ✅ Python packages: `aiohttp`, `tqdm`, `argostranslate`
- ✅ Download script: `scripts/download_models.py`
- ✅ Pre-created directories: `models/stt`, `models/translate/argos-packages`, `models/tts/coqui-models`

**Environment Variables Set:**
```dockerfile
PYTHONUNBUFFERED=1
ARGOS_PACKAGES_DIR=/app/models/translate/argos-packages
```

**What It Downloads:**
- Vosk STT models: English, Hindi, Telugu, Gujarati, Bengali (~1GB)
- Argos translation packages: en↔hi, en↔bn
- (TTS models auto-download at runtime)

**Runs Once:** Container exits after successful download

---

### **docker-compose.yml** (Production)
**Purpose:** Production deployment with automatic model downloading

**Services:**

#### 1. `model-downloader`
```yaml
Dockerfile: docker/Dockerfile.downloader
Volume: voice-models:/app/models
Command: python scripts/download_models.py
Restart: no (runs once)
```

**Contains:**
- Downloads all models to shared volume
- Exits with success code when complete
- Must complete before app starts

#### 2. `voice-translator`
```yaml
Dockerfile: docker/Dockerfile
Port: 7860:7860
Volume: voice-models:/app/models
Depends: model-downloader (service_completed_successfully)
Restart: unless-stopped
```

**Environment Variables:**
```yaml
# Server
HOST=0.0.0.0
PORT=7860
LOG_LEVEL=INFO
ENVIRONMENT=production

# Model Paths
ARGOS_PACKAGES_DIR=/app/models/translate/argos-packages

# Warm Start (Preload Models)
STT_ENABLE_WARM_START=True
STT_PRELOAD_LANGUAGES=en,hi
TRANSLATION_ENABLE_WARM_START=True
TRANSLATION_WARM_START_MODE=common
TRANSLATION_COMMON_PAIRS=en-hi,hi-en,en-bn,bn-en
TTS_ENABLE_WARM_START=True
TTS_PRELOAD_LANGUAGES=en,hi,bn,ta

# Cache Directories
NUMBA_CACHE_DIR=/tmp/numba_cache
XDG_CACHE_HOME=/tmp
HOME=/app

# Python Settings
SPACY_NO_DOWNLOADS=1
PIP_NO_INPUT=1
PIP_USER=0
```

**Health Check:**
```yaml
Test: curl -f http://localhost:7860/health
Interval: 30s
Timeout: 10s
Retries: 3
Start Period: 60s
```

**Volume:**
```yaml
voice-models:
  name: voice-models
```
- Named volume for persistence
- Survives container restarts
- Shared between downloader and app

---

### **docker-compose.local.yml** (Development)
**Purpose:** Development setup using local models (faster startup)

**Services:**

#### 1. `voice-translator` (Only Service)
```yaml
Dockerfile: docker/Dockerfile
Port: 7860:7860
Volume: ../models:/app/models:ro (read-only)
Restart: unless-stopped
```

**Key Differences from Production:**
- ❌ No model-downloader service
- ✅ Mounts local `models/` directory
- ✅ Read-only mount (`:ro`) for safety
- ✅ Faster startup (no download wait)
- ✅ Uses models from host filesystem

**Same Environment Variables as Production**

**When to Use:**
- Development and testing
- When models are already downloaded locally
- Rapid iteration without rebuilds
- Debugging model issues

---

## 🔍 Quick Comparison

| Aspect | Dockerfile | Dockerfile.downloader |
|--------|-----------|----------------------|
| **Purpose** | Run the app | Download models |
| **Base Image** | python:3.11-slim | python:3.11-slim |
| **System Packages** | build-essential, portaudio, ffmpeg, etc. | unzip, curl |
| **Python Packages** | Full requirements.txt | aiohttp, tqdm, argostranslate |
| **spaCy Model** | ✅ Pre-installed | ❌ Not needed |
| **Runtime User** | appuser (non-root) | root |
| **Exposed Port** | 7860 | None |
| **Runs** | Continuously | Once then exits |

| Aspect | docker-compose.yml | docker-compose.local.yml |
|--------|-------------------|-------------------------|
| **Purpose** | Production | Development |
| **Services** | 2 (downloader + app) | 1 (app only) |
| **Model Source** | Docker volume | Local filesystem |
| **First Run** | Slow (downloads) | Fast (uses local) |
| **Model Persistence** | Docker volume | Host filesystem |
| **Best For** | Production, CI/CD | Development, testing |

---

## 📝 Environment Variables Reference

### Model Paths
```bash
# STT Models (configured in app/config/settings.py)
VOSK_MODEL_PATH_EN=/app/models/stt/vosk-en
VOSK_MODEL_PATH_HI=/app/models/stt/vosk-hi
VOSK_MODEL_PATH_TE=/app/models/stt/vosk-te
VOSK_MODEL_PATH_GU=/app/models/stt/vosk-gu
VOSK_MODEL_PATH_BN=/app/models/stt/vosk-bn

# Translation
ARGOS_PACKAGES_DIR=/app/models/translate/argos-packages

# TTS (auto-downloads to this location)
XDG_CACHE_HOME=/tmp  # Coqui downloads to $XDG_CACHE_HOME/.local/share/tts/
```

### Warm Start Configuration
```bash
# STT
STT_ENABLE_WARM_START=True           # Enable preloading
STT_PRELOAD_LANGUAGES=en,hi          # Languages to preload

# Translation
TRANSLATION_ENABLE_WARM_START=True
TRANSLATION_WARM_START_MODE=common   # 'common' or 'all'
TRANSLATION_COMMON_PAIRS=en-hi,hi-en,en-bn,bn-en

# TTS
TTS_ENABLE_WARM_START=True
TTS_PRELOAD_LANGUAGES=en,hi,bn,ta    # Languages to preload
```

### Server Configuration
```bash
HOST=0.0.0.0                         # Listen on all interfaces
PORT=7860                            # Server port
WORKERS=1                            # Worker count
LOG_LEVEL=INFO                       # Logging level
ENVIRONMENT=production               # Environment name
DEBUG=False                          # Debug mode
```

### Python/System Settings
```bash
PYTHONUNBUFFERED=1                   # Immediate stdout/stderr
SPACY_NO_DOWNLOADS=1                 # Don't download spaCy models
PIP_NO_INPUT=1                       # Non-interactive pip
PIP_USER=0                           # Don't use --user flag
NUMBA_CACHE_DIR=/tmp/numba_cache     # Numba compilation cache
HOME=/app                            # User home directory
```

---

## 🚀 Usage Patterns

### Production Deployment
```bash
cd docker
docker-compose up --build
```
**What happens:**
1. Builds `Dockerfile.downloader` → model-downloader service
2. Runs `python scripts/download_models.py` → downloads ~1GB
3. Downloader exits successfully
4. Builds `Dockerfile` → voice-translator service
5. App starts with models from volume
6. Warm start preloads en + hi models

### Development Setup
```bash
cd docker
docker-compose -f docker-compose.local.yml up --build
```
**What happens:**
1. Builds `Dockerfile` → voice-translator service
2. Mounts local `models/` directory
3. App starts immediately
4. Warm start preloads from local models

### Clean Rebuild
```bash
cd docker
docker-compose down -v              # Remove containers and volumes
docker-compose up --build           # Fresh build and download
```

### Check Downloaded Models
```bash
# List volume contents
docker run --rm -v voice-models:/models alpine ls -laR /models

# Expected output:
# /models/stt/vosk-en/
# /models/stt/vosk-hi/
# /models/translate/argos-packages/*.argosmodel
```

---

## 🎯 Which File to Edit?

| Task | File to Edit |
|------|-------------|
| Change Python dependencies | `requirements.txt` + rebuild `Dockerfile` |
| Add system packages | `Dockerfile` (RUN apt-get install) |
| Change model download URLs | `scripts/download_models.py` |
| Add new language to warm start | `docker-compose.yml` (STT_PRELOAD_LANGUAGES) |
| Change server port | `docker-compose.yml` (ports: "7860:7860") |
| Switch to local models | Use `docker-compose.local.yml` |
| Add new download package | `Dockerfile.downloader` (RUN pip install) |
| Configure environment variables | `docker-compose.yml` or `docker-compose.local.yml` |
| Change health check | `docker-compose.yml` (healthcheck section) |
| Modify app code | `app/` directory + rebuild |

---

## 🔧 Troubleshooting Quick Links

| Issue | Check This File |
|-------|----------------|
| Models not downloading | `Dockerfile.downloader` + `docker-compose.yml` command |
| Model path errors | `docker-compose.yml` ARGOS_PACKAGES_DIR + volumes |
| Port already in use | `docker-compose.yml` ports section |
| Permission errors | `Dockerfile` USER directive |
| spaCy model missing | `Dockerfile` spaCy installation section |
| Slow startup | `docker-compose.yml` warm start settings |
| Container won't start | `Dockerfile` healthcheck + app logs |
| Volume issues | `docker-compose.yml` volumes section |

---

## 📚 Related Documentation

- **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** - Full deployment guide
- **[DOCKER_MODEL_SETUP.md](DOCKER_MODEL_SETUP.md)** - Model setup troubleshooting
- **[../GETTING_STARTED.md](../GETTING_STARTED.md)** - General setup guide
- **[../API_DOCUMENTATION.md](../API_DOCUMENTATION.md)** - API reference
- **[../TESTING_GUIDE.md](../TESTING_GUIDE.md)** - Testing procedures

---

## 💡 Pro Tips

1. **Fast Development:** Use `docker-compose.local.yml` with pre-downloaded models
2. **Production:** Use `docker-compose.yml` for clean, reproducible deployments
3. **Debugging:** Check logs with `docker logs voice-translator-app -f`
4. **Volume Inspection:** Use `docker run --rm -v voice-models:/models alpine ls -la /models`
5. **Clean Slate:** Run `docker-compose down -v` to remove everything and start fresh
6. **Health Check:** `curl http://localhost:7860/health` should return `{"status":"healthy"}`
7. **Model Caching:** The `voice-models` volume persists between container restarts
8. **Rebuild Optimization:** Change only what you need to minimize rebuild time

---

**Last Updated:** January 6, 2026
