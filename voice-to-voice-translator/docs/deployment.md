# Deployment Guide

## Overview

This guide covers deploying the Voice-to-Voice Translator in various environments, from local development to production cloud deployments.

## Prerequisites

### System Requirements

**Minimum**:
- CPU: 4 cores
- RAM: 4GB
- Storage: 10GB
- Network: 10 Mbps

**Recommended**:
- CPU: 8 cores or GPU (CUDA-capable)
- RAM: 8GB+
- Storage: 20GB SSD
- Network: 100 Mbps

### Software Requirements
- Python 3.9+
- pip or conda
- Docker (optional)
- Redis (optional, for scaling)

## Local Development Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd voice-to-voice-translator
```

### 2. Create Virtual Environment
```bash
# Using venv
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Using conda
conda create -n voice-translator python=3.9
conda activate voice-translator
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Download Models
```bash
python scripts/download_models.py
```

This will download:
- Vosk models for English and Hindi (~500MB each)
- Argos Translate packages (~200MB per language pair)
- Coqui TTS models (~100MB per language)

### 5. Configure Environment
```bash
cp .env.example .env
```

Edit `.env`:
```ini
HOST=127.0.0.1
PORT=8000
DEBUG=True
LOG_LEVEL=DEBUG
```

### 6. Run Server
```bash
python app/main.py
```

Server will start at `ws://localhost:8000/ws`

### 7. Health Check
```bash
curl http://localhost:8000/health
```

## Docker Deployment

### Single Container

#### Build Image
```bash
docker build -f docker/Dockerfile -t voice-translator:latest .
```

#### Run Container
```bash
docker run -d \
  --name voice-translator \
  -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  voice-translator:latest
```

### Docker Compose

#### Configuration
```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - LOG_LEVEL=INFO
    restart: unless-stopped
```

#### Deploy
```bash
docker-compose up -d
```

#### View Logs
```bash
docker-compose logs -f app
```

#### Stop
```bash
docker-compose down
```

## Production Deployment

### Architecture Options

#### Option 1: Single Server
Best for: < 50 concurrent users

```
Internet → Load Balancer → Application Server
```

#### Option 2: Multi-Server with Load Balancer
Best for: 50-500 concurrent users

```
Internet → Load Balancer → [App Server 1, App Server 2, App Server N]
                              ↓
                         Shared Redis (for session state)
```

#### Option 3: Microservices
Best for: 500+ concurrent users

```
Internet → API Gateway → [WebSocket Servers]
                          ↓
                        Message Queue
                          ↓
          [STT Workers] [Translation Workers] [TTS Workers]
                          ↓
                      Shared Storage
```

### Cloud Deployment

#### AWS Deployment

**Using EC2**:

1. **Launch Instance**
```bash
# Ubuntu 22.04 LTS
# Instance type: t3.xlarge (4 vCPU, 16GB RAM)
# Storage: 30GB gp3
```

2. **Setup Script**
```bash
#!/bin/bash
# setup-aws.sh

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python
sudo apt-get install -y python3.9 python3-pip python3-venv

# Install dependencies
sudo apt-get install -y build-essential libssl-dev libffi-dev
sudo apt-get install -y portaudio19-dev

# Clone and setup application
git clone <repository-url>
cd voice-to-voice-translator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Download models
python scripts/download_models.py

# Setup systemd service
sudo cp deployment/voice-translator.service /etc/systemd/system/
sudo systemctl enable voice-translator
sudo systemctl start voice-translator
```

3. **Systemd Service**
```ini
# /etc/systemd/system/voice-translator.service
[Unit]
Description=Voice-to-Voice Translator
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/voice-to-voice-translator
Environment="PATH=/home/ubuntu/voice-to-voice-translator/venv/bin"
ExecStart=/home/ubuntu/voice-to-voice-translator/venv/bin/python app/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

4. **Application Load Balancer**
- Create ALB with WebSocket support
- Configure health check: `/health`
- Enable sticky sessions
- SSL/TLS termination

**Using ECS (Fargate)**:

1. **Create Task Definition**
```json
{
  "family": "voice-translator",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskRole",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "ACCOUNT.dkr.ecr.REGION.amazonaws.com/voice-translator:latest",
      "cpu": 2048,
      "memory": 4096,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "HOST", "value": "0.0.0.0"},
        {"name": "PORT", "value": "8000"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/voice-translator",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096"
}
```

#### Google Cloud Platform

**Using Compute Engine**:

```bash
# Create instance
gcloud compute instances create voice-translator \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --machine-type=n1-standard-4 \
  --boot-disk-size=30GB \
  --tags=http-server,https-server

# SSH and setup
gcloud compute ssh voice-translator
# Run setup script (similar to AWS)
```

**Using Cloud Run**:

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/voice-translator

# Deploy
gcloud run deploy voice-translator \
  --image gcr.io/PROJECT_ID/voice-translator \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --use-http2
```

#### Azure Deployment

**Using Container Instances**:

```bash
# Create resource group
az group create --name voice-translator-rg --location eastus

# Create container
az container create \
  --resource-group voice-translator-rg \
  --name voice-translator \
  --image REGISTRY.azurecr.io/voice-translator:latest \
  --cpu 4 \
  --memory 8 \
  --ports 8000 \
  --environment-variables \
    HOST=0.0.0.0 \
    PORT=8000
```

### Kubernetes Deployment

#### Deployment YAML

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-translator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: voice-translator
  template:
    metadata:
      labels:
        app: voice-translator
    spec:
      containers:
      - name: app
        image: voice-translator:latest
        ports:
        - containerPort: 8000
        env:
        - name: HOST
          value: "0.0.0.0"
        - name: PORT
          value: "8000"
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: voice-translator-service
spec:
  type: LoadBalancer
  selector:
    app: voice-translator
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
```

#### Deploy

```bash
kubectl apply -f k8s/deployment.yaml
kubectl get services
```

### Scaling Strategies

#### Horizontal Scaling

**Nginx Load Balancer**:

```nginx
# /etc/nginx/nginx.conf
upstream voice_translator {
    least_conn;  # Use least connections algorithm
    
    server 10.0.1.10:8000 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8000 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:8000 max_fails=3 fail_timeout=30s;
}

map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 80;
    server_name api.example.com;

    location /ws {
        proxy_pass http://voice_translator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location /health {
        proxy_pass http://voice_translator;
    }
}
```

#### Vertical Scaling

Increase resources per instance:
- More CPU cores
- More RAM
- GPU acceleration
- Faster storage (NVMe SSD)

### Monitoring and Logging

#### Prometheus Metrics

```python
# Add to main.py
from prometheus_client import Counter, Histogram, Gauge

requests_total = Counter('requests_total', 'Total requests')
latency = Histogram('request_latency_seconds', 'Request latency')
active_connections = Gauge('active_connections', 'Active WS connections')
```

#### Grafana Dashboard

Import dashboard from `monitoring/grafana-dashboard.json`

#### Log Aggregation

**ELK Stack**:
```yaml
# docker-compose.elk.yml
version: '3.8'
services:
  elasticsearch:
    image: elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
    ports:
      - "9200:9200"
  
  logstash:
    image: logstash:8.5.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
  
  kibana:
    image: kibana:8.5.0
    ports:
      - "5601:5601"
```

### Security Hardening

#### SSL/TLS Configuration

**Nginx with Let's Encrypt**:
```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.example.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

#### Firewall Rules

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

#### Environment Variables Security

```bash
# Use secrets management
# AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id voice-translator-secrets

# Kubernetes Secrets
kubectl create secret generic voice-translator-secrets \
  --from-literal=jwt-secret=your-secret-key
```

### Backup and Disaster Recovery

#### Database Backups
```bash
# Backup script
#!/bin/bash
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup models
tar -czf $BACKUP_DIR/models_$DATE.tar.gz models/

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz .env

# Upload to S3
aws s3 cp $BACKUP_DIR/*.tar.gz s3://voice-translator-backups/
```

### Performance Tuning

#### OS-Level Optimizations

```bash
# Increase file descriptors
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# TCP tuning
cat >> /etc/sysctl.conf <<EOF
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 4096
net.ipv4.ip_local_port_range = 1024 65535
EOF

sysctl -p
```

### Troubleshooting

#### Common Issues

**High Memory Usage**:
```bash
# Check memory
free -h

# Limit model memory
export OMP_NUM_THREADS=4
```

**Connection Timeouts**:
```bash
# Check WebSocket settings
grep -i timeout .env
```

**Model Loading Failures**:
```bash
# Verify models
ls -lh models/stt/
python scripts/health_check.py
```

### Health Checks

```python
# Endpoint: /health
{
  "status": "healthy",
  "timestamp": "2025-12-17T10:30:00Z",
  "version": "1.0.0",
  "components": {
    "stt": "ok",
    "translation": "ok",
    "tts": "ok",
    "redis": "ok"
  },
  "metrics": {
    "active_connections": 42,
    "total_requests": 15234,
    "uptime_seconds": 86400
  }
}
```

## Deployment Checklist

- [ ] Environment variables configured
- [ ] Models downloaded and verified
- [ ] SSL/TLS certificates installed
- [ ] Firewall rules configured
- [ ] Monitoring and logging setup
- [ ] Backup strategy implemented
- [ ] Load testing completed
- [ ] Health checks passing
- [ ] Documentation updated
- [ ] Rollback plan prepared
