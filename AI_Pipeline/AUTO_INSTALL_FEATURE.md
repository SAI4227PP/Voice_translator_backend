# Auto-Installation Feature

## 🚀 Overview

The translation system now automatically downloads and installs Argos Translate packages on-demand when a user requests translation for a language pair that isn't installed yet.

---

## 🔄 Complete Flow

### 1. **User Request**
```bash
POST /translate
{
    "text": "Hello, how are you?",
    "source_language": "en",
    "target_language": "hi"
}
```

### 2. **API Validation** (`main.py`)
- ✅ Checks if source language is supported
- ✅ Checks if target language is supported
- ✅ Checks if language pair exists in default list
- ✅ Calls translator

### 3. **Translator Check** (`translator.py`)
```python
async def translate(text, source_lang, target_lang):
    # Check if package is installed
    if not engine.is_language_pair_available(source_lang, target_lang):
        # Auto-install
        await _ensure_package_installed(source_lang, target_lang)
```

### 4. **Auto-Installation** (`argos_engine.py`)
```python
async def install_language_pair(source_lang, target_lang):
    # Run in executor to avoid blocking
    return await loop.run_in_executor(
        None,
        _install_language_pair_sync,
        source_lang,
        target_lang
    )

def _install_language_pair_sync(source_lang, target_lang):
    1. Update package index
    2. Find package for language pair
    3. Download package
    4. Install from path
    5. Update installed packages list
    6. Clear translation cache
    7. Return success
```

### 5. **Translation Execution**
- If installed successfully → Perform translation
- If installation failed → Raise error with helpful message

---

## 📋 Key Components

### File: `translator.py`

**Method: `_ensure_package_installed()`**
- Checks if package is already installed
- Triggers auto-installation if needed
- Returns success/failure status
- Logs all actions

**Method: `translate()`**
- Tries direct translation first
- Falls back to bridge translation (via English) for Indian languages
- Auto-installs packages before each translation attempt
- Provides clear error messages if installation fails

### File: `argos_engine.py`

**Method: `install_language_pair()` (async)**
- Wrapper that runs installation in executor
- Ensures non-blocking operation

**Method: `_install_language_pair_sync()` (sync)**
- Updates Argos Translate package index
- Searches for specific language pair
- Downloads the package
- Installs to `/tmp/argostranslate` (configurable)
- Updates internal package list
- Clears translation cache

**Method: `is_language_pair_available()`**
- Checks if a specific language pair is installed
- Used before translation attempts

---

## 🎯 Supported Scenarios

### Direct Translation
```
en → hi  (English to Hindi)
├─ Check if installed
├─ Auto-install if needed
└─ Translate directly
```

### Bridge Translation
```
hi → te  (Hindi to Telugu)
├─ Check if hi→te installed (not available in Argos)
├─ Use English as bridge:
│   ├─ Check if hi→en installed
│   ├─ Auto-install hi→en if needed
│   ├─ Check if en→te installed
│   └─ Auto-install en→te if needed
├─ Translate: hi → en
└─ Translate: en → te
```

---

## 📊 Logging

### Installation Logs
```
[info] package_not_found_attempting_install source=en target=hi
[info] auto_installing_translation_package source=en target=hi
[info] installing_translation_package source=en target=hi
[info] available_packages_count count=156 source=en target=hi
[info] found_package_to_install source=en target=hi package_name=translate-en_hi-1_9
[info] downloading_translation_package source=en target=hi package=translate-en_hi-1_9
[info] package_downloaded path=/tmp/argostranslate/translate-en_hi-1_9.argosmodel
[info] package_installed_from_path path=/tmp/argostranslate/translate-en_hi-1_9.argosmodel
[info] translation_cache_cleared
[info] translation_package_installed_successfully source=en target=hi total_packages=1
[info] direct_translation source=en target=hi
```

### Error Logs
```
[warning] translation_package_not_found_in_repo source=en target=xyz
[error] permission_error_installing_package source=en target=hi error=...
[error] failed_to_install_translation_package source=en target=hi error=...
```

---

## ⚙️ Configuration

### Environment Variables
```bash
# Directory for Argos packages (default: /tmp/argostranslate)
ARGOS_PACKAGES_DIR=/tmp/argostranslate

# Home directory for package downloads (default: /tmp)
HOME=/tmp
```

### Docker Configuration
These are set in `main.py` before imports:
```python
os.environ['ARGOS_PACKAGES_DIR'] = '/tmp/argostranslate'
os.environ.setdefault('HOME', '/tmp')
```

---

## 🔒 Error Handling

### Package Not Found
```json
{
    "detail": "Language pair en→xyz not available and could not be installed. Package may not exist in Argos Translate repository."
}
```

### Permission Error
```json
{
    "detail": "Translation failed: Permission denied installing package"
}
```

### Network Error
```json
{
    "detail": "Translation failed: Failed to download package"
}
```

---

## 📈 Performance

### First Request (with installation)
```
Request: en → hi
├─ Package check: ~5ms
├─ Package download: ~500-2000ms (depends on network)
├─ Package install: ~100-300ms
├─ Translation: ~50-100ms
└─ Total: ~650-2400ms
```

### Subsequent Requests (cached)
```
Request: en → hi
├─ Package check: ~1ms (already installed)
├─ Translation: ~50-100ms (LRU cached if same text)
└─ Total: ~50-100ms
```

---

## ✅ Benefits

1. **Zero Manual Setup**
   - No need to pre-download packages
   - Users can immediately use any supported language pair

2. **Automatic Scaling**
   - System adapts to actual usage patterns
   - Only downloads packages that are used

3. **Transparent to Users**
   - First request might be slower
   - All subsequent requests are fast
   - No action required from users

4. **Resource Efficient**
   - Only installs packages when needed
   - Doesn't waste space on unused language pairs

5. **Fault Tolerant**
   - Gracefully handles installation failures
   - Provides clear error messages
   - Logs all actions for debugging

---

## 🧪 Testing

### Test Direct Translation
```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "source_language": "en",
    "target_language": "es"
  }'
```

### Test Bridge Translation
```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "नमस्ते",
    "source_language": "hi",
    "target_language": "te"
  }'
```

### Monitor Logs
```bash
docker-compose logs -f app | grep -E "install|package|translation"
```

---

## 🎊 Conclusion

The auto-installation feature makes the translation system **production-ready** without requiring manual package management. Users get:

- ✅ Instant access to 150+ language pairs
- ✅ Automatic package downloads on first use
- ✅ Fast subsequent translations
- ✅ Clear error messages
- ✅ Full logging for troubleshooting

The system is now truly **plug-and-play**! 🚀
