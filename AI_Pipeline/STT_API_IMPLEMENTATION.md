# STT API Implementation Summary

## Overview
This document summarizes the Speech-to-Text (STT) REST API implementation for the Voice Translator Backend.

## Implementation Date
January 7, 2026

## What Was Implemented

### 1. Request/Response Models
Added Pydantic models in [app/main.py](app/main.py):
- **STTRequest**: For single audio transcription via base64-encoded data
- **BatchSTTRequest**: For batch audio transcription

### 2. REST API Endpoints

#### 2.1 POST /stt/transcribe
- **Purpose**: Transcribe base64-encoded audio to text
- **Input**: JSON with base64-encoded audio data, language code, sample rate
- **Output**: Transcribed text with optional confidence score
- **Use Case**: Direct API integration, mobile apps, web clients

#### 2.2 POST /stt/transcribe-file
- **Purpose**: Transcribe uploaded audio file to text
- **Input**: Multipart form data with audio file upload
- **Output**: Transcribed text with file metadata
- **Use Case**: File-based transcription, web forms, batch processing

#### 2.3 POST /stt/transcribe-batch
- **Purpose**: Transcribe multiple audio files in one request
- **Input**: JSON array of base64-encoded audio files
- **Output**: Array of transcription results
- **Use Case**: Batch processing, high-throughput scenarios

### 3. Documentation
Updated [API_DOCUMENTATION.md](API_DOCUMENTATION.md) with:
- Complete endpoint specifications (sections 14-16)
- Request/response examples
- cURL examples
- Python code examples
- Error handling documentation
- Status codes and error responses

## Technical Details

### Architecture
- **STT Engine**: Vosk (existing implementation)
- **Factory Pattern**: Uses existing STTFactory for engine creation
- **Async Processing**: All endpoints are async for better performance
- **Error Handling**: Comprehensive error handling with appropriate HTTP status codes

### Supported Languages
The API supports all languages for which Vosk models are downloaded:
- English (en)
- Hindi (hi)
- Telugu (te)
- Gujarati (gu)
- Bengali (bn)
- Additional languages as models are added

### Request Validation
- Base64 decoding validation
- Language support checking via ModelScanner
- File size limits (10MB max for file uploads)
- Batch size limits (50 items max)

### Response Format
All endpoints return JSON with:
- Transcribed text
- Language code
- Processing time in milliseconds
- Optional confidence scores
- Error messages for failed transcriptions

## Files Modified

1. **app/main.py**
   - Added imports: `File`, `Form`, `UploadFile` from FastAPI
   - Added request models: `STTRequest`, `BatchSTTRequest`
   - Implemented 3 new endpoints: `/stt/transcribe`, `/stt/transcribe-file`, `/stt/transcribe-batch`

2. **API_DOCUMENTATION.md**
   - Added sections 14-16 for STT endpoints
   - Included comprehensive examples and documentation

## Usage Examples

### Example 1: Basic Transcription
```python
import requests
import base64

# Encode audio file
with open("audio.wav", "rb") as f:
    audio_base64 = base64.b64encode(f.read()).decode()

# Transcribe
response = requests.post(
    "http://localhost:8000/stt/transcribe",
    json={
        "audio_data": audio_base64,
        "language": "en",
        "return_confidence": True
    }
)

result = response.json()
print(f"Text: {result['text']}")
print(f"Confidence: {result.get('confidence')}")
```

### Example 2: File Upload
```python
import requests

# Upload and transcribe
with open("recording.wav", "rb") as f:
    response = requests.post(
        "http://localhost:8000/stt/transcribe-file",
        files={"file": f},
        data={"language": "en", "return_confidence": True}
    )

result = response.json()
print(f"Text: {result['text']}")
print(f"File size: {result['file_size']} bytes")
```

### Example 3: Batch Transcription
```python
import requests
import base64

# Encode multiple files
audio_files = []
for filename in ["audio1.wav", "audio2.wav", "audio3.wav"]:
    with open(filename, "rb") as f:
        audio_files.append(base64.b64encode(f.read()).decode())

# Batch transcribe
response = requests.post(
    "http://localhost:8000/stt/transcribe-batch",
    json={
        "audio_files": audio_files,
        "language": "en",
        "return_confidence": True
    }
)

result = response.json()
for t in result['transcriptions']:
    print(f"[{t['index']}] {t['text']}")
```

## Testing Recommendations

### 1. Unit Testing
Test the following scenarios:
- Valid audio transcription (various formats)
- Invalid base64 data handling
- Unsupported language handling
- File size limit enforcement
- Batch processing with mixed success/failure

### 2. Integration Testing
- End-to-end transcription workflow
- Performance testing with various audio lengths
- Concurrent request handling
- Error recovery

### 3. Load Testing
- Batch endpoint with maximum items (50)
- Concurrent requests to multiple endpoints
- Large file uploads (near 10MB limit)

## Error Handling

The API returns appropriate HTTP status codes:
- **200 OK**: Successful transcription
- **400 Bad Request**: Invalid audio data or malformed request
- **401 Unauthorized**: Missing or invalid authentication (if enabled)
- **413 Payload Too Large**: File exceeds size limit
- **422 Unprocessable Entity**: Unsupported language
- **500 Internal Server Error**: Server-side transcription failure

## Performance Considerations

1. **Async Processing**: All endpoints use async/await for non-blocking execution
2. **Engine Caching**: STTFactory caches engines per language
3. **Recognizer Management**: Creates new recognizer per request for thread safety
4. **Batch Optimization**: Processes multiple files efficiently in batch endpoint

## Future Enhancements

Potential improvements for future versions:
1. Streaming STT endpoint for real-time transcription
2. Support for additional audio formats (automatic conversion)
3. Word-level timestamps in transcription results
4. Language auto-detection
5. Custom vocabulary support
6. Speaker diarization
7. Punctuation and capitalization post-processing

## Dependencies

The implementation uses existing components:
- `app.pipeline.stt.STTFactory`: Engine factory
- `app.utils.model_scanner.ModelScanner`: Language detection
- `app.config`: Logging and settings
- FastAPI framework for API handling
- Vosk for speech recognition

## Notes

- All endpoints respect existing authentication and rate limiting if enabled
- File uploads are limited to 10MB to prevent resource exhaustion
- Batch requests are limited to 50 items per request
- Audio must be in PCM16 or WAV format (as required by Vosk)
- Sample rate should match the model's expected rate (typically 16000 Hz)

## Related Files

- [app/main.py](app/main.py) - Main API implementation
- [app/pipeline/stt/vosk_engine.py](app/pipeline/stt/vosk_engine.py) - STT engine
- [app/pipeline/stt/stt_factory.py](app/pipeline/stt/stt_factory.py) - Factory pattern
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - Complete API documentation
- [app/config/settings.py](app/config/settings.py) - Configuration settings

## Support

For issues or questions:
1. Check the API documentation
2. Review error messages in server logs
3. Verify audio format and encoding
4. Ensure language models are downloaded
5. Check authentication if enabled
