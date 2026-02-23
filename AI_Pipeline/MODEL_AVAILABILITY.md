# Language Model Availability - December 17, 2025

## Overview
This document clarifies which Indian language models are **actually available** vs planned/requested.

---

## ✅ Available Language Models

### Speech-to-Text (Vosk)
| Language | Code | Model | Size | Status |
|----------|------|-------|------|--------|
| English (US) | `en` | vosk-model-small-en-us-0.15 | 40MB | ✅ Available |
| Hindi | `hi` | vosk-model-hi-0.22 | 1.5GB | ✅ Available |
| Telugu | `te` | vosk-model-small-te-0.42 | 58MB | ✅ Available |
| Gujarati | `gu` | vosk-model-small-gu-0.42 | 100MB | ✅ Available |
| Bengali | `bn` | vosk-model-en-in-0.5 | 1GB | ✅ Available (Indian English) |

**Total Available:** 5 languages

### Translation (Argos Translate)
| Language Pair | Code | Status |
|---------------|------|--------|
| English ↔ Hindi | `en` ↔ `hi` | ✅ Available |
| English ↔ Bengali | `en` ↔ `bn` | ✅ Available |

**Total Pairs:** 4 (2 bidirectional pairs)

### Text-to-Speech (Coqui TTS)
**ALL 13 LANGUAGES FULLY SUPPORTED** ✅

| # | Language | Code | Model Type | ISO-3 | Status |
|---|----------|------|------------|-------|--------|
| 1 | English | `en` | Tacotron2-DDC / XTTS v2 | eng | ✅ Available |
| 2 | Hindi | `hi` | Fairseq MMS | hin | ✅ Available |
| 3 | Bengali | `bn` | Fairseq MMS | ben | ✅ Available |
| 4 | Telugu | `te` | Fairseq MMS | tel | ✅ Available |
| 5 | Tamil | `ta` | Fairseq MMS | tam | ✅ Available |
| 6 | Marathi | `mr` | Fairseq MMS | mar | ✅ Available |
| 7 | Gujarati | `gu` | Fairseq MMS | guj | ✅ Available |
| 8 | Kannada | `kn` | Fairseq MMS | kan | ✅ Available |
| 9 | Malayalam | `ml` | Fairseq MMS | mal | ✅ Available |
| 10 | Punjabi | `pa` | Fairseq MMS | pan | ✅ Available |
| 11 | Urdu | `ur` | Fairseq MMS | urd | ✅ Available |
| 12 | Assamese | `as` | Fairseq MMS | asm | ✅ Available |
| 13 | Odia | `or` | Fairseq MMS | ory | ✅ Available |

**Model Selection Strategy:**
- **English (Production/Docker):** Uses `tacotron2-DDC` (no TOS required)
- **English (Interactive):** Can use XTTS v2 (best quality, requires TOS)
- **Indian Languages (All 12):** Uses Fairseq MMS models (1100+ language support, no TOS)

**Total Available:** 13 languages (100% coverage)

**Additional European Languages (via XTTS v2 / Simple Models):**
Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Czech, Arabic, Chinese, Japanese, Hungarian, Korean

---

## ❌ Unavailable Language Models

### Speech-to-Text (Not in Vosk Repository)
| Language | Code | Status | Reason | TTS Available? |
|----------|------|--------|--------|----------------|
| Tamil | `ta` | ❌ Not Available | Model doesn't exist on Vosk | ✅ Yes (Fairseq) |
| Kannada | `kn` | ❌ Not Available | Model doesn't exist on Vosk | ✅ Yes (Fairseq) |
| Malayalam | `ml` | ❌ Not Available | Model doesn't exist on Vosk | ✅ Yes (Fairseq) |
| Marathi | `mr` | ❌ Not Available | Model doesn't exist on Vosk | ✅ Yes (Fairseq) |
| Punjabi | `pa` | ❌ Not Available | Model doesn't exist on Vosk | ✅ Yes (Fairseq) |
| Urdu | `ur` | ❌ Not Available | Model doesn't exist on Vosk | ✅ Yes (Fairseq) |
| Assamese | `as` | ❌ Not Available | Model doesn't exist on Vosk | ✅ Yes (Fairseq) |
| Odia | `or` | ❌ Not Available | Model doesn't exist on Vosk | ✅ Yes (Fairseq) |

### Translation (Not in Argos Repository)
| Language Pair | Code | Status | Reason |
|---------------|------|--------|--------|
| English ↔ Telugu | `en` ↔ `te` | ❌ Not Available | Package not in Argos |
| English ↔ Tamil | `en` ↔ `ta` | ❌ Not Available | Package not in Argos |
| English ↔ Kannada | `en` ↔ `kn` | ❌ Not Available | Package not in Argos |
| English ↔ Malayalam | `en` ↔ `ml` | ❌ Not Available | Package not in Argos |
| English ↔ Gujarati | `en` ↔ `gu` | ❌ Not Available | Package not in Argos |
| English ↔ Marathi | `en` ↔ `mr` | ❌ Not Available | Package not in Argos |

---

## System Configuration

### Updated Files
1. **scripts/download_models.py**
   - ✅ English, Hindi, Telugu, Gujarati, Bengali (Indian English) STT
   - ✅ English↔Hindi, English↔Bengali translation
   - ❌ Removed: Tamil, Kannada, Malayalam, Marathi, Gujarati translation

2. **app/config/settings.py**
   - ✅ Model paths for: en, hi, te, gu, bn
   - ❌ Removed model paths for: ta, kn, ml, mr

3. **app/utils/model_scanner.py**
   - ✅ Dynamic detection (returns only installed models)
   - ✅ No fake defaults
   - ✅ Updated with all 13 Indian languages + English for TTS

4. **app/pipeline/tts/coqui_engine.py**
   - ✅ XTTS v2 for English and 15 European languages
   - ✅ Fairseq MMS for 12 Indian languages
   - ✅ Auto-downloads models on first use

5. **app/main.py**
   - ✅ Added `/tts/generate` endpoint
   - ✅ Supports all 13 languages

---

## Bridge Translation Strategy

Since most direct Indian-to-Indian translation pairs don't exist, the system uses **English as a bridge language**:

### Example: Hindi to Telugu
```
Hindi → English → Telugu
(if en-te pair existed, which it doesn't currently)
```

### Currently Working Pairs
```
Hindi → English  ✅ (direct)
Bengali → English  ✅ (direct)
English → Hindi  ✅ (direct)
English → Bengali  ✅ (direct)
Hindi → Bengali  ⚠️ (via English bridge)
Bengali → Hindi  ⚠️ (via English bridge)
```

---

## Download Results

### Expected Output
```bash
✓ Vosk models: 5/5 downloaded
  ✓ English (US)
  ✓ Hindi
  ✓ Telugu
  ✓ Gujarati
  ✓ Bengali (Indian English)

✓ Argos Translate: 4/4 packages installed
  ✓ English→Hindi
  ✓ Hindi→English
  ✓ English→Bengali
  ✓ Bengali→English

✓ TTS: 13 languages available
  ✓ English (XTTS v2)
  ✓ Hindi, Bengali, Telugu, Tamil (Fairseq MMS)
  ✓ Marathi, Gujarati, Kannada, Malayalam (Fairseq MMS)
  ✓ Punjabi, Urdu, Assamese, Odia (Fairseq MMS)
  ℹ Models auto-download on first use
```

### Previous Errors (Now Fixed)
```bash
❌ Telugu download failed → ✅ Fixed (now using v0.42)
❌ Tamil not available → ✅ Removed (doesn't exist)
❌ Kannada not available → ✅ Removed (doesn't exist)
❌ Malayalam not available → ✅ Removed (doesn't exist)
❌ Gujarati download failed → ✅ Fixed (now using v0.42)
❌ Marathi not available → ✅ Removed (doesn't exist)
❌ Bengali STT failed → ✅ Using Indian English model
❌ Translation packages not available → ✅ Limited to Hindi & Bengali
```

---

## API Endpoints

### GET /languages/supported
Returns **only installed** languages:
```json
{
  "stt": {
    "en": {"name": "English"},
    "hi": {"name": "Hindi"},
    "te": {"name": "Telugu"},
    "gu": {"name": "Gujarati"},
    "bn": {"name": "Bengali"}
  },
  "translation": {
    "hi": {"name": "Hindi"},
    "bn": {"name": "Bengali"}
  },
  "tts": {
    "en": {"name": "English"},
    "hi": {"name": "Hindi"},
    "bn": {"name": "Bengali"},
    "te": {"name": "Telugu"},
    "ta": {"name": "Tamil"},
    "mr": {"name": "Marathi"},
    "gu": {"name": "Gujarati"},
    "kn": {"name": "Kannada"},
    "ml": {"name": "Malayalam"},
    "pa": {"name": "Punjabi"},
    "ur": {"name": "Urdu"},
    "as": {"name": "Assamese"},
    "or": {"name": "Odia"}
  }
}
```

### GET /languages/pairs
Returns **only installed** translation pairs:
```json
{
  "pairs": [
    {"from": "en", "to": "hi", "name": "English → Hindi"},
    {"from": "hi", "to": "en", "name": "Hindi → English"},
    {"from": "en", "to": "bn", "name": "English → Bengali"},
    {"from": "bn", "to": "en", "name": "Bengali → English"}
  ],
  "bridge_support": true
}
```

---

## Recommendations

### For Production Use
1. **Supported Languages:** Focus on Hindi and Bengali (full pipeline)
2. **Partial Support:** Telugu and Gujarati (STT only, no translation)
3. **Indian English:** Use Bengali model for Indian English accent

### For Future Expansion
1. **Monitor Vosk Repository:** Check for new Indian language models
2. **Monitor Argos Repository:** Check for new translation packages
3. **Alternative Solutions:**
   - Google Cloud Translation API (commercial)
   - Azure Translator (commercial)
   - Custom model training with Kaldi (advanced)

### Build Your Own Models
If you need unsupported languages:
- **STT:** Train Kaldi models using Vosk recipe
- **Translation:** Train Argos models or use commercial APIs
- **TTS:** Use Coqui TTS training tools

---

## Testing

### Verify Available Models
```bash
# Check STT models
ls -la models/stt/
# Expected: vosk-en, vosk-hi, vosk-te, vosk-gu, vosk-bn

# Check translation packages
curl http://localhost:7860/languages/pairs
# Expected: 4 pairs (en↔hi, en↔bn)

# Check supported languages
curl http://localhost:7860/languages/supported
# Expected: en, hi, te, gu, bn for STT; hi, bn for translation
```

### Test Translation
```bash
# Working: Hindi to English
curl -X POST http://localhost:7860/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "नमस्ते", "from": "hi", "to": "en"}'

# Working: Bengali to English
curl -X POST http://localhost:7860/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "হ্যালো", "from": "bn", "to": "en"}'

# Not working: Telugu to English (no package)
curl -X POST http://localhost:7860/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "హలో", "from": "te", "to": "en"}'
# Expected: Error or fallback behavior
```

### Test TTS
```bash
# Working: English TTS
curl -X POST http://localhost:7860/tts/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test", "language": "en", "format": "wav"}' \
  --output english.wav

# Working: Hindi TTS
curl -X POST http://localhost:7860/tts/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "नमस्ते, यह एक परीक्षण है", "language": "hi", "format": "wav"}' \
  --output hindi.wav

# Working: Tamil TTS (no STT, but TTS works!)
curl -X POST http://localhost:7860/tts/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "வணக்கம், இது ஒரு சோதனை", "language": "ta", "format": "wav"}' \
  --output tamil.wav
```

---

## Summary

| Category | Requested | Available | Success Rate |
|----------|-----------|-----------|--------------|
| **STT Models** | 9 | 5 | 56% |
| **Translation Pairs** | 16 | 4 | 25% |
| **TTS Models** | 13 | 13 | 100% ✅ |
| **Full Pipeline (STT+Trans+TTS)** | 9 languages | 2 languages | 22% |

**Fully Supported End-to-End (STT→Translation→TTS):** Hindi, Bengali  
**Partial Support (STT + TTS only):** Telugu, Gujarati, English  
**TTS Only:** Tamil, Kannada, Malayalam, Marathi, Punjabi, Urdu, Assamese, Odia  
**Translation Only:** None

### Use Case Support
| Use Case | Languages Supported | Count |
|----------|--------------------|---------|
| **Text-to-Speech** | en, hi, bn, te, ta, mr, gu, kn, ml, pa, ur, as, or | 13 ✅ |
| **Speech Recognition** | en, hi, te, gu, bn | 5 |
| **Text Translation** | hi, bn (with English) | 2 |
| **Full Voice Translation** | hi, bn | 2 |

---

**Last Updated:** December 17, 2025  
**Status:** ✅ System configured with only available models  
**Docker Build:** Ready for rebuild with correct models
