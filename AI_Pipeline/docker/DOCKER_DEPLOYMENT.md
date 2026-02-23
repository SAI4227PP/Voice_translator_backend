# Docker Deployment Guide

Complete guide for deploying the Voice-to-Voice Translator using Docker.

---

## 📋 Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- At least 8GB RAM
- 20GB free disk space (for models)

---

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd voice-to-voice-translator

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Build and Run

**Option A: Using Docker Compose (Recommended)**

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Check status
docker-compose ps
```

**Option B: Using Docker directly**

```bash
# Build image
docker build -f docker/Dockerfile -t voice-translator:latest .

# Run container
docker run -d \
  --name voice-translator \
  -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/logs:/app/logs \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  voice-translator:latest
```

---

## 🏗️ Build Process

The Dockerfile uses a multi-stage build for optimization:

### Stage 1: Base Image
- Python 3.11 slim
- System dependencies (FFmpeg, PortAudio, etc.)

### Stage 2: Python Dependencies
- Installs all Python packages
- Cached for faster rebuilds

### Stage 3: Model Downloader
- Downloads Vosk models (9 languages)
- Installs Argos Translate packages
- Sets up TTS models

### Stage 4: Production Image
- Copies dependencies and models
- Creates non-root user
- Sets up health checks
- Optimized for production

---

## 🔧 Configuration

### Environment Variables

All configuration is done via environment variables. See `.env.example` for all options.

**Essential Variables:**

```bash
# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Security (IMPORTANT: Change in production!)
JWT_SECRET_KEY=your-very-secure-secret-key-min-32-characters
API_KEYS=key1,key2,key3

# Performance
TRANSLATION_WORKERS=4
TTS_WORKERS=2
MAX_CONNECTIONS=100
```

### Volume Mounts

**Models Volume:**
```yaml
volumes:
  - voice-models:/app/models
```
Persists downloaded models across container restarts.

**Logs Volume:**
```yaml
volumes:
  - voice-logs:/app/logs
```
Persists application logs.

---

## 📊 Resource Requirements

### Minimum Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 10 GB | 20 GB |
| Network | 100 Mbps | 1 Gbps |

### Resource Limits (Docker Compose)

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      cpus: '2'
      memory: 4G
```

---

## 🔍 Health Checks

The container includes automatic health checks:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

**Check health status:**
```bash
docker inspect --format='{{.State.Health.Status}}' voice-translator-app
```

---

## 📝 Logging

### View Logs

```bash
# All logs
docker-compose logs -f

# App logs only
docker-compose logs -f app

# Last 100 lines
docker-compose logs --tail=100 app

# Follow new logs
docker logs -f voice-translator-app
```

### Log Configuration

Logs are configured in `docker-compose.yml`:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

---

## 🔐 Security Best Practices

### 1. Use Non-Root User

The Dockerfile creates and uses a non-root user:

```dockerfile
USER appuser
```

### 2. Secure Secrets

**Never commit secrets to Git!**

```bash
# Use environment variables
export JWT_SECRET_KEY=$(openssl rand -base64 32)

# Or use Docker secrets (Swarm mode)
echo "my-secret" | docker secret create jwt_secret -
```

### 3. Enable Authentication

```bash
ENABLE_AUTH=true
JWT_SECRET_KEY=<your-secure-key>
API_KEYS=key1,key2,key3
```

### 4. Rate Limiting

```bash
MAX_CONNECTIONS_PER_IP=10
MAX_REQUESTS_PER_MINUTE=100
MAX_MESSAGES_PER_SECOND=10
```

---

## 🌐 Nginx Reverse Proxy (Optional)

### nginx.conf

```nginx
upstream voice_translator {
    least_conn;
    server app:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # WebSocket support
    location / {
        proxy_pass http://voice_translator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running connections
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

### Enable in docker-compose.yml

Uncomment the nginx service and add your config:

```yaml
nginx:
  image: nginx:alpine
  container_name: voice-translator-nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf:ro
  depends_on:
    - app
```

---

## 📈 Monitoring (Optional)

### Enable Prometheus + Grafana

Uncomment services in `docker-compose.yml`:

```bash
docker-compose up -d prometheus grafana
```

**Access:**
- Prometheus: http://localhost:9091
- Grafana: http://localhost:3000 (admin/admin)

### Metrics Endpoint

```bash
curl http://localhost:9090/metrics
```

---

## 🔄 Scaling

### Horizontal Scaling

```bash
# Scale app service
docker-compose up -d --scale app=3

# Use load balancer (nginx) to distribute
```

### Vertical Scaling

Adjust resources in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '8'
      memory: 16G
```

---

## 🛠️ Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs app

# Check status
docker ps -a

# Inspect container
docker inspect voice-translator-app
```

### Out of Memory

```bash
# Increase memory limit
docker-compose down
# Edit docker-compose.yml memory limit
docker-compose up -d
```

### Models Not Loading

```bash
# Check model directory
docker exec voice-translator-app ls -la /app/models/stt

# Re-download models
docker exec voice-translator-app python scripts/download_models.py
```

### WebSocket Connection Issues

```bash
# Check if port is exposed
docker port voice-translator-app

# Test WebSocket
wscat -c ws://localhost:8000/ws
```

### Permission Errors

```bash
# Fix volume permissions
sudo chown -R 1000:1000 ./models ./logs
```

---

## 🔄 Updates and Maintenance

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Update Models

```bash
# Download new models
docker exec voice-translator-app python scripts/download_models.py

# Restart to load new models
docker-compose restart app
```

### Backup Data

```bash
# Backup models
docker run --rm -v voice-models:/source -v $(pwd)/backup:/backup alpine \
  tar -czf /backup/models-backup.tar.gz -C /source .

# Backup logs
docker run --rm -v voice-logs:/source -v $(pwd)/backup:/backup alpine \
  tar -czf /backup/logs-backup.tar.gz -C /source .
```

### Restore Data

```bash
# Restore models
docker run --rm -v voice-models:/target -v $(pwd)/backup:/backup alpine \
  tar -xzf /backup/models-backup.tar.gz -C /target
```

---

## 📦 Production Deployment Checklist

- [ ] Set secure `JWT_SECRET_KEY` (min 32 characters)
- [ ] Configure `API_KEYS` for authentication
- [ ] Set `ENABLE_AUTH=true`
- [ ] Configure `CORS_ORIGINS` with specific domains
- [ ] Set up SSL/TLS (use nginx with Let's Encrypt)
- [ ] Configure rate limits
- [ ] Set resource limits
- [ ] Enable monitoring (Prometheus/Grafana)
- [ ] Set up log aggregation
- [ ] Configure backup strategy
- [ ] Test health checks
- [ ] Set up alerting
- [ ] Document deployment process
- [ ] Test disaster recovery

---

## 🚨 Emergency Procedures

### Stop All Services

```bash
docker-compose down
```

### Force Restart

```bash
docker-compose restart
```

### Remove Everything (CAUTION!)

```bash
# Stop and remove containers, networks, volumes
docker-compose down -v

# Remove all images
docker rmi voice-translator:latest
```

---

## 📞 Support

For issues:
1. Check logs: `docker-compose logs -f app`
2. Verify health: `curl http://localhost:8000/health`
3. Check resources: `docker stats`
4. Review configuration: `docker-compose config`

---

## 🎯 Next Steps

1. **Configure environment variables** in `.env`
2. **Start services**: `docker-compose up -d`
3. **Verify health**: `curl http://localhost:8000/health`
4. **Test WebSocket**: Connect a client
5. **Monitor logs**: `docker-compose logs -f`
6. **Set up monitoring** (optional)
7. **Configure SSL** for production
8. **Deploy to cloud** (AWS, GCP, Azure)

---

**Version:** 1.0.0  
**Last Updated:** December 17, 2025
