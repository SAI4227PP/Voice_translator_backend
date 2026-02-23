# Docker Compose Usage Guide

## Problem: Model Downloader Runs Every Time

When running `docker-compose up --build`, the model-downloader keeps running because:
- `--build` forces image rebuild
- Rebuild triggers the downloader service
- Models are already in the volume but the service runs anyway

## ✅ Solution: Use Correct Commands

### First Time Setup (Download Models)

```powershell
cd docker

# Build and download models (only needed once)
docker-compose up --build

# Wait for completion, then stop
docker-compose down
```

### Regular Usage (After Models Downloaded)

```powershell
cd docker

# Start without rebuilding (much faster!)
docker-compose up -d

# Or just start the app
docker-compose up voice-translator -d
```

### When You Need to Rebuild

```powershell
# Only rebuild the app, not the downloader
docker-compose build voice-translator
docker-compose up -d

# Or rebuild everything but skip downloader
docker-compose up --build --no-deps voice-translator -d
```

## 📋 Command Reference

| Command | When to Use | Models Downloaded? |
|---------|-------------|-------------------|
| `docker-compose up` | First time or after clearing volumes | ✅ Yes |
| `docker-compose up -d` | Regular startup (fast) | ❌ No |
| `docker-compose up --build` | Code changes + first time | ✅ Yes |
| `docker-compose build voice-translator` | Only rebuild app | ❌ No |
| `docker-compose up voice-translator -d` | Start only app | ❌ No |

## 🎯 Recommended Workflow

### Initial Setup (Once)
```powershell
cd docker
docker-compose up --build
# Wait for models to download (~2-5 minutes)
# Press Ctrl+C when you see "Ready to Start!"
docker-compose down
```

### Daily Usage
```powershell
cd docker
docker-compose up -d  # Fast startup, uses existing models
```

### After Code Changes
```powershell
cd docker
docker-compose build voice-translator  # Only rebuild app
docker-compose restart voice-translator  # Restart with new code
```

### After Dependency Changes (requirements.txt)
```powershell
cd docker
docker-compose build --no-cache voice-translator
docker-compose up -d
```

## 🔧 Alternative: Use Local Models

To completely avoid the downloader:

```powershell
cd docker

# Use local models configuration
docker-compose -f docker-compose.local.yml up --build
```

This mounts your local `models/` directory and skips the downloader entirely.

## 🚫 Stop Model Downloader from Running

If models are already downloaded and you want to skip the downloader:

### Option 1: Start Only the App
```powershell
# Skip downloader, start only the app
docker-compose up voice-translator -d
```

### Option 2: Remove Downloader Temporarily
Edit `docker-compose.yml` and comment out the dependency:

```yaml
voice-translator:
  # depends_on:
  #   model-downloader:
  #     condition: service_completed_successfully
```

Then:
```powershell
docker-compose up -d
```

### Option 3: Use docker-compose.local.yml
```powershell
# This doesn't have a downloader at all
docker-compose -f docker-compose.local.yml up -d
```

## 📊 Check if Models Exist

```powershell
# Check volume contents
docker run --rm -v voice-models:/models alpine ls -la /models/stt/

# Should show:
# vosk-en/
# vosk-hi/
```

If models exist, you don't need to run the downloader again.

## 🔄 Full Reset (If Needed)

```powershell
# Stop everything
docker-compose down

# Remove volumes (this deletes models!)
docker volume rm voice-models

# Start fresh (will download models again)
docker-compose up --build
```

## 💡 Best Practices

1. **First time:** Use `docker-compose up --build` to download models
2. **Daily use:** Use `docker-compose up -d` (no build, no download)
3. **Code changes:** Use `docker-compose build voice-translator` then `restart`
4. **Save time:** Use `docker-compose.local.yml` if you have local models
5. **Check models:** Use `docker volume inspect voice-models` to verify

## 🎓 Understanding the Services

```yaml
model-downloader:
  restart: "no"          # Runs once and exits
  command: python scripts/download_models.py
  # Downloads models to volume if not present

voice-translator:
  depends_on:
    model-downloader:
      condition: service_completed_successfully
  # Waits for downloader to finish before starting
```

The downloader:
- ✅ Runs automatically on first `docker-compose up`
- ✅ Skips files that already exist
- ✅ Exits after completion
- ✅ Won't run again unless you rebuild the image
- ❌ **Will run every time you use `--build`** ← This is your issue!

## 🎯 Quick Fix for Your Issue

**Stop using `--build` after initial setup:**

```powershell
# ❌ DON'T do this after first time
docker-compose up --build

# ✅ DO this instead
docker-compose up -d
```

**Or skip the downloader entirely:**

```powershell
# ✅ Use local models
docker-compose -f docker-compose.local.yml up -d
```

## 📝 Summary

**The Problem:**
- `docker-compose up --build` rebuilds images
- Rebuilding triggers the model-downloader service
- Even though models exist, the service runs

**The Solution:**
- Use `docker-compose up -d` for regular startups
- Only use `--build` when you actually need to rebuild
- Or use `docker-compose.local.yml` to skip the downloader entirely

**Quick Commands:**
```powershell
# First time only
docker-compose up --build

# After that, always use
docker-compose up -d

# Or use local models
docker-compose -f docker-compose.local.yml up -d
```
