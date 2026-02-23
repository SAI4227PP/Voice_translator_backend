# Quick Start: TTS Warm Start Configuration

## Enable Warm Start (Recommended for Production)

Add to your `.env` file or environment variables:

```env
# Enable TTS warm start (default: true)
TTS_ENABLE_WARM_START=true

# Languages to preload at startup (comma-separated)
# Adjust based on your most frequently used languages
TTS_PRELOAD_LANGUAGES=en,hi,es,fr

# Example for Indian languages
# TTS_PRELOAD_LANGUAGES=en,hi,bn,te,ta,mr,gu,kn,ml,pa

# Example for European languages
# TTS_PRELOAD_LANGUAGES=en,es,fr,de,it,pt,ru

# Example minimal (only English and Hindi)
# TTS_PRELOAD_LANGUAGES=en,hi
```

## Disable Warm Start (Development/Testing)

```env
TTS_ENABLE_WARM_START=false
```

## Docker Configuration

### docker-compose.yml
```yaml
services:
  voice-translator:
    environment:
      - TTS_ENABLE_WARM_START=true
      - TTS_PRELOAD_LANGUAGES=en,hi,es,fr,de,it
```

### Dockerfile
```dockerfile
ENV TTS_ENABLE_WARM_START=true
ENV TTS_PRELOAD_LANGUAGES=en,hi,es,fr
```

## Supported Languages

| Code | Language | Model Type |
|------|----------|------------|
| `en` | English | Tacotron2 |
| `hi` | Hindi | Fairseq MMS |
| `es` | Spanish | Tacotron2 |
| `fr` | French | Tacotron2 |
| `de` | German | Tacotron2 |
| `it` | Italian | Tacotron2 |
| `pt` | Portuguese | VITS |
| `ru` | Russian | VITS |
| `zh` | Chinese | Tacotron2 |
| `ja` | Japanese | Tacotron2 |
| `bn` | Bengali | Fairseq MMS |
| `te` | Telugu | Fairseq MMS |
| `ta` | Tamil | Fairseq MMS |
| `mr` | Marathi | Fairseq MMS |
| `gu` | Gujarati | Fairseq MMS |
| `kn` | Kannada | Fairseq MMS |
| `ml` | Malayalam | Fairseq MMS |
| `pa` | Punjabi | Fairseq MMS |

## Verify Configuration

After starting the application, check logs:

```bash
# Check if warm start is enabled
docker logs voice-translator | grep "tts_warm_start_initializing"

# Check preloaded languages
docker logs voice-translator | grep "tts_model_preloaded_successfully"

# Check total warm start time
docker logs voice-translator | grep "tts_warm_start_complete"
```

Expected output:
```
INFO: tts_warm_start_initializing languages=['en', 'hi', 'es', 'fr'] count=4
INFO: tts_model_preloaded_successfully language=en
INFO: tts_model_preloaded_successfully language=hi
INFO: tts_model_preloaded_successfully language=es
INFO: tts_model_preloaded_successfully language=fr
INFO: tts_warm_start_complete total_time_seconds=9.2 successfully_loaded=['en', 'hi', 'es', 'fr'] failed_to_load=[]
```

## Performance Testing

Test first TTS request speed:

```bash
time curl -X POST http://localhost:8000/tts/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "language": "en", "format": "wav"}' \
  -o test.wav
```

**With warm start:** Response time should be **<1 second**  
**Without warm start:** First request would take **3-10 seconds**

## Troubleshooting

### High Memory Usage
Reduce preloaded languages:
```env
TTS_PRELOAD_LANGUAGES=en,hi  # Only essential languages
```

### Slow Startup
This is expected! Trade-off for faster first requests.
Typical: 5-15 seconds depending on language count.

### Models Not Loading
Check error logs:
```bash
docker logs voice-translator | grep "tts_model_preload_failed"
```

## Default Configuration

If you don't set these variables, defaults are:
- `TTS_ENABLE_WARM_START=true` (enabled)
- `TTS_PRELOAD_LANGUAGES=en,hi,es,fr` (4 languages)

## Recommendations by Use Case

### High-Traffic Production
```env
TTS_ENABLE_WARM_START=true
TTS_PRELOAD_LANGUAGES=en,hi,es,fr,de,it,pt,ru  # All major languages
```

### Indian Market Focus
```env
TTS_ENABLE_WARM_START=true
TTS_PRELOAD_LANGUAGES=en,hi,bn,te,ta,mr,gu  # Indian languages
```

### Single Language (English Only)
```env
TTS_ENABLE_WARM_START=true
TTS_PRELOAD_LANGUAGES=en  # Minimal
```

### Development/Testing
```env
TTS_ENABLE_WARM_START=false  # Faster restarts
```

## That's It!

With these simple environment variables, you can control TTS warm start behavior without any code changes. Enable it for production to get instant TTS responses from the first request!
