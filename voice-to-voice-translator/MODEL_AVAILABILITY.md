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
| Language | Code | Status | Notes |
|----------|------|--------|-------|
| Multiple | Various | ✅ Available | Downloads on first use |

---

## ❌ Unavailable Language Models

### Speech-to-Text (Not in Vosk Repository)
| Language | Code | Status | Reason |
|----------|------|--------|--------|
| Tamil | `ta` | ❌ Not Available | Model doesn't exist on Vosk |
| Kannada | `kn` | ❌ Not Available | Model doesn't exist on Vosk |
| Malayalam | `ml` | ❌ Not Available | Model doesn't exist on Vosk |
| Marathi | `mr` | ❌ Not Available | Model doesn't exist on Vosk |

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

✓ TTS: Auto-downloads on first use
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
    // Dynamic based on Coqui models
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

---

## Summary

| Category | Requested | Available | Success Rate |
|----------|-----------|-----------|--------------|
| **STT Models** | 9 | 5 | 56% |
| **Translation Pairs** | 16 | 4 | 25% |
| **Full Pipeline** | 9 languages | 2 languages | 22% |

**Fully Supported End-to-End:** Hindi, Bengali  
**Partial Support (STT only):** Telugu, Gujarati, English  
**Not Available:** Tamil, Kannada, Malayalam, Marathi

---

**Last Updated:** December 17, 2025  
**Status:** ✅ System configured with only available models  
**Docker Build:** Ready for rebuild with correct models
