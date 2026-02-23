# TTS Terms of Service (TOS) Fix

## Problem
XTTS v2 model requires interactive Terms of Service agreement, which fails in Docker/non-interactive environments with:
```
EOFError: EOF when reading a line
```

## Root Cause
- XTTS v2 has `'tos_required': True` in model metadata
- Coqui TTS library tries to prompt for TOS agreement via `input()`
- In Docker/headless environments, `stdin` is not available → EOF error

## Solutions Implemented

### 1. Environment Variables
Added two environment variables to bypass TOS prompt:

```bash
COQUI_TOS_AGREED=1          # Signals agreement to Coqui TTS
TTS_USE_SIMPLE_MODELS=true  # Use non-TOS models by default
```

### 2. Programmatic TOS Agreement
Created `_agree_to_tos()` method that:
- Creates `.tos_agreed` file in model cache directory
- Works in both normal and Docker environments
- Handles permission issues gracefully

### 3. Model Selection Strategy
Updated `_get_default_model()` to:
- Use simple models (no TOS) in non-interactive environments
- Detect if running in Docker/headless mode
- Fallback to language-specific models instead of XTTS v2

### 4. Error Handling
Enhanced error handling to:
- Catch `EOFError` specifically for TOS prompt failures
- Provide clear error messages with solutions
- Log detailed context for debugging

## Model Selection Logic

### Production/Docker (Non-Interactive)
```python
# English and European languages
"en" → "tts_models/en/ljspeech/tacotron2-DDC"  # No TOS required
"es" → "tts_models/es/mai/tacotron2-DDC"
"fr" → "tts_models/fr/mai/tacotron2-DDC"
...

# Indian languages (Fairseq - No TOS required)
"hi" → "tts_models/hin/fairseq/vits"
"bn" → "tts_models/ben/fairseq/vits"
...
```

### Development/Interactive (Optional)
```python
# All languages can use XTTS v2 if TOS is agreed
"en", "es", "fr", ... → "tts_models/multilingual/multi-dataset/xtts_v2"
```

## Files Modified

1. **app/pipeline/tts/coqui_engine.py**
   - Added `_agree_to_tos()` method
   - Enhanced `_load_model()` with TOS handling
   - Updated `_get_default_model()` with fallback logic
   - Set `COQUI_TOS_AGREED` environment variable

2. **docker/Dockerfile**
   - Added `COQUI_TOS_AGREED=1`
   - Added `TTS_USE_SIMPLE_MODELS=true`

3. **.env**
   - Added TTS configuration section
   - Documented environment variables

## Configuration

### Docker Deployment
```dockerfile
ENV COQUI_TOS_AGREED=1 \
    TTS_USE_SIMPLE_MODELS=true
```

### Local Development
```bash
# .env file
TTS_USE_SIMPLE_MODELS=false  # Use XTTS v2 for better quality
COQUI_TOS_AGREED=1           # Pre-agreed to TOS
```

## Testing

### Test TTS Endpoint
```bash
# Should work without TOS prompt
curl -X POST http://localhost:8000/tts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test",
    "language": "en",
    "format": "wav"
  }' \
  --output test.wav
```

### Verify Model Used
Check logs for:
```
using_simple_tts_model | language=en | model=tts_models/en/ljspeech/tacotron2-DDC | reason=non-interactive environment
```

## Benefits

✅ **No Interactive Prompts** - Works in Docker/CI/CD  
✅ **Graceful Fallback** - Uses alternative models if TOS fails  
✅ **Clear Error Messages** - Helpful debugging information  
✅ **Configurable** - Easy to switch between simple/XTTS models  
✅ **Production Ready** - Handles all edge cases  

## Supported Languages (After Fix)

### With Simple Models
- English, Spanish, French, German, Italian, Portuguese, Russian, Chinese, Japanese
- All 12 Indian languages (Hindi, Bengali, Telugu, Tamil, etc.) via Fairseq

### Quality Comparison
| Model Type | Quality | TOS Required | Docker Compatible |
|------------|---------|--------------|-------------------|
| XTTS v2 | ⭐⭐⭐⭐⭐ | ✅ Yes | ⚠️ With fix |
| Simple Models | ⭐⭐⭐⭐ | ❌ No | ✅ Yes |
| Fairseq MMS | ⭐⭐⭐⭐ | ❌ No | ✅ Yes |

## Migration Guide

### Existing Deployments
1. Pull latest code changes
2. Rebuild Docker image: `docker-compose build`
3. Update `.env` with new TTS variables
4. Restart services: `docker-compose up -d`

### No Changes Needed If:
- Using Docker (fix is automatic)
- Using non-XTTS models already
- TOS already agreed locally

## Future Improvements

1. **Download Simple Models** - Pre-download in Docker build
2. **Model Quality Config** - Choose quality vs compatibility
3. **TOS Agreement UI** - Web interface for TOS agreement
4. **Model Caching** - Cache frequently used models

---

**Status:** ✅ Fixed and Deployed  
**Last Updated:** December 18, 2025  
**Tested:** Docker, Local, Production environments
