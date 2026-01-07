# STT API Quick Reference Guide

## Endpoints Overview

| Endpoint | Method | Purpose | Max Size/Items |
|----------|--------|---------|----------------|
| `/stt/transcribe` | POST | Transcribe base64 audio | N/A |
| `/stt/transcribe-file` | POST | Transcribe uploaded file | 10MB |
| `/stt/transcribe-batch` | POST | Batch transcription | 50 items |

## Quick Start Examples

### 1. Simple Transcription (Base64)

```python
import requests
import base64

with open("audio.wav", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://localhost:8000/stt/transcribe",
    json={
        "audio_data": audio_b64,
        "language": "en"
    }
)

print(response.json()["text"])
```

### 2. File Upload

```python
import requests

with open("audio.wav", "rb") as f:
    response = requests.post(
        "http://localhost:8000/stt/transcribe-file",
        files={"file": f},
        data={"language": "en"}
    )

print(response.json()["text"])
```

### 3. Batch Processing

```python
import requests
import base64

# Prepare multiple audio files
audio_files = []
for filename in ["audio1.wav", "audio2.wav"]:
    with open(filename, "rb") as f:
        audio_files.append(base64.b64encode(f.read()).decode())

# Batch request
response = requests.post(
    "http://localhost:8000/stt/transcribe-batch",
    json={
        "audio_files": audio_files,
        "language": "en"
    }
)

for item in response.json()["transcriptions"]:
    print(f"[{item['index']}] {item['text']}")
```

## cURL Examples

### Transcribe Base64
```bash
AUDIO_B64=$(base64 -w 0 audio.wav)
curl -X POST http://localhost:8000/stt/transcribe \
  -H "Content-Type: application/json" \
  -d "{\"audio_data\":\"$AUDIO_B64\",\"language\":\"en\"}"
```

### Upload File
```bash
curl -X POST http://localhost:8000/stt/transcribe-file \
  -F "file=@audio.wav" \
  -F "language=en"
```

### Batch Transcription
```bash
curl -X POST http://localhost:8000/stt/transcribe-batch \
  -H "Content-Type: application/json" \
  -d '{
    "audio_files": ["'$(base64 -w 0 audio1.wav)'", "'$(base64 -w 0 audio2.wav)'"],
    "language": "en"
  }'
```

## Response Format

### Success Response
```json
{
  "text": "transcribed text here",
  "language": "en",
  "processing_time_ms": 123.45,
  "confidence": 0.95  // optional
}
```

### Error Response
```json
{
  "detail": {
    "error": "Language 'xyz' is not supported for STT",
    "available_languages": ["en", "hi", "te"],
    "message": "Check /languages/supported for available STT languages"
  }
}
```

## Supported Languages

Check dynamically via API:
```bash
curl http://localhost:8000/languages/supported
```

Common languages (if models are downloaded):
- `en` - English
- `hi` - Hindi
- `te` - Telugu
- `gu` - Gujarati
- `bn` - Bengali

## Parameters Reference

### STTRequest
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| audio_data | string | ✅ Yes | - | Base64-encoded audio (PCM16/WAV) |
| language | string | ✅ Yes | - | Language code (e.g., 'en') |
| sample_rate | integer | ❌ No | 16000 | Sample rate in Hz |
| return_confidence | boolean | ❌ No | false | Include confidence score |

### File Upload
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| file | file | ✅ Yes | - | Audio file (WAV, MP3, etc.) |
| language | string | ❌ No | "en" | Language code |
| return_confidence | boolean | ❌ No | false | Include confidence score |

### BatchSTTRequest
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| audio_files | array | ✅ Yes | - | Array of base64 audio (max 50) |
| language | string | ✅ Yes | - | Language code for all files |
| sample_rate | integer | ❌ No | 16000 | Sample rate in Hz |
| return_confidence | boolean | ❌ No | false | Include confidence scores |

## Error Codes

| Status Code | Meaning | Common Causes |
|-------------|---------|---------------|
| 200 | Success | - |
| 400 | Bad Request | Invalid base64, malformed JSON |
| 401 | Unauthorized | Missing/invalid auth token |
| 413 | Payload Too Large | File > 10MB |
| 422 | Unprocessable Entity | Unsupported language |
| 500 | Internal Server Error | STT engine failure |

## Best Practices

### Audio Format
- ✅ **Recommended**: 16-bit PCM WAV, 16000 Hz, mono
- ✅ **Supported**: Most common audio formats
- ❌ **Avoid**: Very high sample rates, multi-channel audio

### Performance Tips
1. Use batch endpoint for multiple files
2. Keep audio files under 10MB
3. Use appropriate sample rate (16000 Hz recommended)
4. Reuse connections for multiple requests

### Error Handling
```python
try:
    response = requests.post(url, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    print(result["text"])
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 422:
        print(f"Unsupported language: {e.response.json()}")
    else:
        print(f"HTTP error: {e}")
except requests.exceptions.Timeout:
    print("Request timed out")
except Exception as e:
    print(f"Error: {e}")
```

## Testing

Run the test suite:
```bash
cd tests
python test_stt_api.py
```

Create a test audio file:
```python
import wave
import numpy as np

# Generate 1 second of test audio
sample_rate = 16000
duration = 1
t = np.linspace(0, duration, sample_rate * duration)
audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

# Save as WAV
with wave.open("test_audio.wav", "w") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    f.writeframes(audio.tobytes())
```

## Integration Examples

### JavaScript/Node.js
```javascript
const fs = require('fs');
const axios = require('axios');

// Read and encode audio
const audio = fs.readFileSync('audio.wav');
const audioBase64 = audio.toString('base64');

// Transcribe
axios.post('http://localhost:8000/stt/transcribe', {
  audio_data: audioBase64,
  language: 'en'
})
.then(response => {
  console.log('Text:', response.data.text);
})
.catch(error => {
  console.error('Error:', error.response.data);
});
```

### Python with Authentication
```python
import requests
import base64

# Get token (if auth enabled)
token_response = requests.post(
    "http://localhost:8000/auth/token",
    json={"user_id": "user123"}
)
token = token_response.json()["token"]

# Transcribe with auth
with open("audio.wav", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://localhost:8000/stt/transcribe",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "audio_data": audio_b64,
        "language": "en"
    }
)

print(response.json()["text"])
```

## Troubleshooting

### Issue: "Language not supported"
**Solution**: Check available languages via `/languages/supported` endpoint

### Issue: "Invalid base64 audio data"
**Solution**: Ensure proper base64 encoding without newlines
```python
# Correct
audio_b64 = base64.b64encode(audio_bytes).decode()

# Incorrect (has newlines)
audio_b64 = base64.encodebytes(audio_bytes).decode()
```

### Issue: "File too large"
**Solution**: Compress audio or split into chunks (max 10MB)

### Issue: Poor transcription quality
**Solutions**:
- Use correct language code
- Ensure audio is clear and not distorted
- Use recommended sample rate (16000 Hz)
- Check that Vosk model is properly installed

## Related Documentation

- [Full API Documentation](../API_DOCUMENTATION.md)
- [STT Implementation Details](../STT_API_IMPLEMENTATION.md)
- [Vosk Engine Documentation](../app/pipeline/stt/vosk_engine.py)
- [Test Suite](test_stt_api.py)

## Support

For issues or questions:
1. Check this quick reference
2. Review full API documentation
3. Run test suite to verify setup
4. Check server logs for errors
5. Verify Vosk models are downloaded
