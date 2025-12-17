# Quick Test Guide - Language API Fix

## 🧪 Testing the Fixes

### 1. Quick Local Test (Without Docker)

If you have Python environment set up:

```bash
# Navigate to project directory
cd voice-to-voice-translator

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Run the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then test the endpoints:

```bash
# Test supported languages endpoint
curl http://localhost:8000/languages/supported

# Test translation pairs endpoint
curl http://localhost:8000/languages/pairs

# Test health check
curl http://localhost:8000/health
```

### 2. Docker Test (Recommended)

```bash
# Navigate to docker directory
cd voice-to-voice-translator/docker

# Rebuild image with fixes
docker-compose build --no-cache

# Start container
docker-compose up -d

# Watch logs
docker-compose logs -f app

# Wait for "Application startup complete" message
```

Then test:

```bash
# Test from host machine
curl http://localhost:8000/languages/supported
curl http://localhost:8000/languages/pairs
```

### 3. Expected Results

#### ✅ Successful Response for `/languages/supported`:

```json
{
  "stt": {
    "en": {
      "name": "English",
      "model": "vosk-en",
      "path": "models/stt/vosk-en"
    },
    "hi": {
      "name": "Hindi",
      "model": "vosk-hi",
      "path": "models/stt/vosk-hi"
    },
    "es": {
      "name": "Spanish",
      "model": "vosk-es",
      "path": "models/stt/vosk-es"
    }
  },
  "translation": {
    "en": {"name": "English"},
    "hi": {"name": "Hindi"},
    "es": {"name": "Spanish"},
    "fr": {"name": "French"},
    "de": {"name": "German"},
    "it": {"name": "Italian"},
    "pt": {"name": "Portuguese"},
    "ru": {"name": "Russian"},
    "zh": {"name": "Chinese"},
    "ja": {"name": "Japanese"},
    "ko": {"name": "Korean"},
    "ar": {"name": "Arabic"},
    "nl": {"name": "Dutch"},
    "pl": {"name": "Polish"},
    "tr": {"name": "Turkish"}
  },
  "tts": {
    "en": {
      "name": "English",
      "voices": ["default"]
    },
    "es": {
      "name": "Spanish",
      "voices": ["default"]
    },
    "fr": {
      "name": "French",
      "voices": ["default"]
    },
    "de": {
      "name": "German",
      "voices": ["default"]
    }
  }
}
```

#### ✅ Successful Response for `/languages/pairs`:

```json
{
  "pairs": [
    {"from": "en", "to": "es", "name": "English → Spanish"},
    {"from": "en", "to": "fr", "name": "English → French"},
    {"from": "en", "to": "de", "name": "English → German"},
    {"from": "en", "to": "hi", "name": "English → Hindi"},
    {"from": "es", "to": "en", "name": "Spanish → English"},
    {"from": "fr", "to": "en", "name": "French → English"},
    {"from": "de", "to": "en", "name": "German → English"},
    {"from": "hi", "to": "en", "name": "Hindi → English"}
  ],
  "count": 8
}
```

### 4. Log Verification

Check the logs for these messages (no errors):

```
✅ [info] scanning_stt_models path=models/stt exists=True
✅ [info] no_stt_models_found_using_defaults (or models_found=X)
✅ [info] scanning_translation_packages
✅ [warning] cannot_update_package_index (acceptable warning)
✅ [info] translation_scan_complete languages_found=X
✅ [info] scanning_tts_models
✅ [info] tts_scan_complete models_found=X

❌ NO MORE: [error] permission_error_scanning_translation
❌ NO MORE: RuntimeError: cannot cache function '__o_fold'
```

### 5. What to Look For

**✅ GOOD (These are OK):**
- `[warning] cannot_update_package_index` - Expected when running as non-root
- `[warning] no_stt_models_found_using_defaults` - Expected when models not downloaded
- `[warning] argostranslate_not_available` - Expected if package not installed
- `[warning] coqui_tts_not_available` - Expected if TTS not installed

**❌ BAD (These should NOT appear):**
- `[error] permission_error_scanning_translation`
- `RuntimeError: cannot cache function`
- Any error that causes the endpoints to return empty objects `{}`

### 6. Advanced Testing

Test with Postman or curl:

```bash
# Test with pretty print
curl -s http://localhost:8000/languages/supported | python -m json.tool

# Test response time
time curl -s http://localhost:8000/languages/supported > /dev/null

# Test from different IP (if accessible)
curl http://YOUR_SERVER_IP:8000/languages/supported
```

### 7. Troubleshooting

If endpoints still return empty:

```bash
# Check if server is running
curl http://localhost:8000/health

# Check logs for errors
docker-compose logs -f app | grep -i error

# Restart container
docker-compose restart app

# Check file permissions
docker-compose exec app ls -la /tmp/numba_cache
```

---

## 📊 Summary

**Before Fix:**
- 🔴 Empty response: `{"stt": {}, "translation": {}, "tts": {}}`
- 🔴 Errors in logs
- 🔴 Permission denied errors
- 🔴 Numba caching errors

**After Fix:**
- ✅ Valid response with default languages
- ✅ Clean logs (only warnings)
- ✅ No permission errors
- ✅ No caching errors
- ✅ API works without downloaded models

---

## 🚀 Next Steps

1. ✅ Verify endpoints return data
2. ✅ Check logs are clean
3. ⏭️ Download models (optional): `python scripts/download_models.py`
4. ⏭️ Install translation packages (optional)
5. ⏭️ Test with real audio data

---

**Status: READY TO TEST** 🎉
