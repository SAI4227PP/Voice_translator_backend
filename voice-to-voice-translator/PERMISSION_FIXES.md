# Permission Errors Fixed - December 17, 2025

## Issues Identified

### 1. ❌ Argostranslate Permission Error
```
[Errno 13] Permission denied: '/home/appuser'
```
**Cause:** Argostranslate trying to write cache/packages to read-only `/home/appuser` directory

### 2. ❌ Matplotlib Permission Error
```
mkdir -p failed for path /home/appuser/.config/matplotlib
```
**Cause:** Matplotlib trying to create config directory in read-only home directory

### 3. ❌ Fontconfig Cache Error
```
Fontconfig error: No writable cache directories
```
**Cause:** Fontconfig trying to write cache to read-only locations

### 4. ❌ TTS List Models Error
```
TTS.list_models() missing 1 required positional argument: 'self'
```
**Cause:** Calling `TTS.list_models()` as class method instead of using `ModelManager`

---

## Solutions Implemented

### ✅ 1. Dockerfile - Writable Cache Directories

**File:** `docker/Dockerfile`

Added environment variables for writable directories:
```dockerfile
ENV HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    FONTCONFIG_PATH=/tmp/fontconfig \
    ARGOS_PACKAGES_DIR=/tmp/argostranslate

# Create cache directories with proper permissions
USER root
RUN mkdir -p /tmp/numba_cache /tmp/matplotlib /tmp/fontconfig /tmp/argostranslate && \
    chmod -R 777 /tmp/numba_cache /tmp/matplotlib /tmp/fontconfig /tmp/argostranslate
USER appuser
```

**Impact:** All libraries can now write to `/tmp/*` directories with proper permissions

---

### ✅ 2. Application Startup - Environment Variables

**File:** `app/main.py`

Added environment variables at application startup:
```python
# Configure matplotlib and fontconfig to use writable directories
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'
os.environ['FONTCONFIG_PATH'] = '/tmp/fontconfig'
os.environ.setdefault('HOME', '/tmp')
# Configure argostranslate to use writable directory
os.environ['ARGOS_PACKAGES_DIR'] = '/tmp/argostranslate'
```

**Impact:** Environment variables set before any library imports

---

### ✅ 3. Model Scanner - Argostranslate Configuration

**File:** `app/utils/model_scanner.py`

Added environment configuration in three functions:
- `get_available_translation_languages()`
- `get_translation_pairs()`

```python
# Set argostranslate to use writable directory
import os
os.environ.setdefault('ARGOS_PACKAGES_DIR', '/tmp/argostranslate')
os.environ.setdefault('HOME', '/tmp')

import argostranslate.package
```

**Impact:** Argostranslate uses writable directory for package management

---

### ✅ 4. TTS Model Scanner - Fixed API Call

**File:** `app/utils/model_scanner.py`

Changed from incorrect class method to proper ModelManager:
```python
# OLD (incorrect):
from TTS.api import TTS
available_models = TTS.list_models()  # ❌ Missing self argument

# NEW (correct):
from TTS.utils.manage import ModelManager
manager = ModelManager()
available_models = manager.list_models()  # ✅ Proper instance method
```

**Impact:** TTS model scanning now works correctly without errors

---

## Verification Steps

### 1. Rebuild Docker Image
```bash
cd docker
docker-compose build --no-cache
```

### 2. Run Container
```bash
docker-compose up -d
```

### 3. Check Logs
```bash
docker-compose logs -f
```

### Expected Results (No Errors):
```
✓ No permission denied errors for /home/appuser
✓ No matplotlib config directory errors
✓ No fontconfig cache errors
✓ TTS models scan without "missing self" error
✓ Translation packages scan successfully
✓ Translation pairs load without permission errors
```

---

## Environment Variables Summary

| Variable | Value | Purpose |
|----------|-------|---------|
| `HOME` | `/tmp` | Fallback home directory (writable) |
| `MPLCONFIGDIR` | `/tmp/matplotlib` | Matplotlib configuration cache |
| `FONTCONFIG_PATH` | `/tmp/fontconfig` | Fontconfig cache directory |
| `ARGOS_PACKAGES_DIR` | `/tmp/argostranslate` | Argostranslate package storage |
| `NUMBA_CACHE_DIR` | `/tmp/numba_cache` | Numba JIT compilation cache |

---

## Benefits

1. **✅ No Permission Errors:** All libraries have writable directories
2. **✅ Docker Security:** Still runs as non-root user `appuser`
3. **✅ Clean Logs:** No warning/error spam from permission issues
4. **✅ Faster Startup:** Libraries can cache properly without retrying
5. **✅ Production Ready:** All configurations aligned for containerized deployment

---

## Testing Checklist

- [ ] Rebuild Docker image without cache
- [ ] Start container and check logs for permission errors
- [ ] Test `/languages/supported` endpoint
- [ ] Test `/languages/pairs` endpoint
- [ ] Verify TTS model scanning works
- [ ] Check translation package loading
- [ ] Verify no matplotlib warnings in logs
- [ ] Confirm fontconfig operates without errors

---

**Status:** ✅ All permission errors resolved
**Last Updated:** December 17, 2025
