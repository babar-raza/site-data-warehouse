# Docker Resource Limits Guide

## Overview

This document outlines the resource limits configured for all Docker containers to prevent massive storage/memory growth.

## Resource Limit Summary

### Memory Limits per Service

| Service | Memory Limit | Memory Reservation | CPU Limit | CPU Reservation |
|---------|--------------|-------------------|-----------|-----------------|
| warehouse (PostgreSQL) | 2GB | 512MB | 2.0 | 0.5 |
| ollama | 8GB | 2GB | 4.0 | 2.0 |
| celery_worker | 2GB | - | 2.0 | - |
| insights_engine | 1GB | - | 1.0 | - |
| scheduler | 1GB | - | 1.0 | - |
| startup_orchestrator | 1GB | - | 1.0 | - |
| api_ingestor | 512MB | - | 1.0 | - |
| ga4_ingestor | 512MB | - | 1.0 | - |
| transform | 512MB | - | 0.5 | - |
| insights_api | 512MB | - | 1.0 | - |
| mcp | 512MB | - | 0.5 | - |
| prometheus | 512MB | - | 0.5 | - |
| grafana | 512MB | - | 0.5 | - |
| redis | 512MB | - | 0.5 | - |
| metrics_exporter | 256MB | - | 0.25 | - |

**Total Maximum Memory:** ~20GB
**Total Reserved Memory:** ~3GB

## Log Rotation Configuration

All services have log rotation enabled to prevent log files from growing indefinitely:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"    # Maximum 10MB per log file
    max-file: "3"      # Keep maximum 3 log files
```

**Maximum log storage per container:** 30MB (10MB × 3 files)
**Total maximum log storage:** ~600MB (20 services × 30MB)

## Temporary File System (tmpfs)

All containers have tmpfs mounts for temporary data:

- Large services (database, ollama): 256-512MB
- Medium services (workers, engines): 128-256MB
- Small services (APIs, metrics): 64-128MB

This prevents temporary files from being written to persistent storage.

## Volume Limits

### PostgreSQL Data
- **Volume:** `pgdata`
- **Expected Growth:** ~100MB/day for typical usage
- **Recommendation:** Monitor and set up automated backups

### Prometheus Data
- **Volume:** `prometheus_data`
- **Retention:** Configured in prometheus.yml (default: 15 days)
- **Expected Size:** ~1-2GB for 15 days

### Grafana Data
- **Volume:** `grafana_data`
- **Expected Size:** < 100MB (dashboard configurations only)

### Ollama Data
- **Volume:** `ollama_data`
- **Expected Size:** 5-50GB (depending on models loaded)
- **Recommendation:** Periodically clean unused models

### Redis Data
- **Volume:** `redis_data`
- **Max Memory:** 512MB (configured with maxmemory policy)
- **Eviction:** LRU (Least Recently Used) when limit reached

## Cleanup Policies

### Manual Cleanup

Use the provided cleanup script:
```bash
./scripts/docker-cleanup.sh
```

This script removes:
- Stopped containers
- Dangling images
- Unused volumes (with confirmation)
- Build cache older than 24 hours
- Unused networks

### Automated Cleanup (Recommended)

Add to cron for weekly cleanup:
```bash
# Run every Sunday at 2 AM
0 2 * * 0 /path/to/scripts/docker-cleanup.sh
```

### Docker System Prune

For aggressive cleanup:
```bash
docker system prune -a --volumes -f
```

⚠️ **WARNING:** This removes ALL unused data, including volumes!

## Monitoring Resource Usage

### Real-time Monitoring
```bash
# View live stats for all containers
docker stats

# View stats for specific service
docker stats gsc_warehouse

# One-time snapshot
docker stats --no-stream
```

### Check Disk Usage
```bash
# Docker disk usage summary
docker system df

# Detailed breakdown
docker system df -v
```

### Container-specific Usage
```bash
# Memory usage
docker inspect gsc_warehouse --format='{{.HostConfig.Memory}}'

# CPU usage
docker inspect gsc_warehouse --format='{{.HostConfig.CpuQuota}}'
```

## Best Practices

### 1. Regular Monitoring
- Set up alerts for high memory/CPU usage
- Monitor disk space weekly
- Check log sizes monthly

### 2. Cleanup Schedule
- Run cleanup script weekly
- Remove unused images after updates
- Backup and clear old logs quarterly

### 3. Volume Management
- Set up automated database backups
- Rotate backups (keep last 30 days)
- Monitor volume growth trends

### 4. Resource Tuning
- Adjust limits based on actual usage
- Increase limits for production workloads
- Decrease limits for development

### 5. Build Optimization
- Use `.dockerignore` to reduce image size
- Multi-stage builds where applicable
- Remove build dependencies in final image

## Troubleshooting

### Container Out of Memory (OOM)
```bash
# Check OOM events
docker inspect gsc_warehouse | grep -i oom

# Increase memory limit in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G  # Increased from 2G
```

### Disk Space Full
```bash
# Find large volumes
docker volume ls -q | xargs docker volume inspect | grep -A 5 "Mountpoint"

# Remove specific volume
docker volume rm volume_name

# Clean everything (CAREFUL!)
docker system prune -a --volumes -f
```

### High CPU Usage
```bash
# Find which container
docker stats --no-stream | sort -k 2 -h

# Limit CPU for specific service in docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '0.5'  # Reduced from 1.0
```

### Logs Growing Too Fast
```bash
# Check log sizes
docker inspect --format='{{.LogPath}}' gsc_warehouse | xargs ls -lh

# Clear logs for specific container
truncate -s 0 $(docker inspect --format='{{.LogPath}}' gsc_warehouse)

# Adjust log rotation in docker-compose.yml
logging:
  options:
    max-size: "5m"   # Reduced from 10m
    max-file: "2"    # Reduced from 3
```

## Deployment with Limits

### Initial Deployment
```bash
# Deploy with resource limits
./scripts/docker-deploy-limited.sh core

# Deploy multiple profiles
./scripts/docker-deploy-limited.sh "core insights api observability"
```

### Rebuild and Deploy
```bash
# Rebuild images and deploy
./scripts/docker-deploy-limited.sh core rebuild
```

### Manual Deployment
```bash
# Stop containers
docker-compose down

# Start with specific profile
docker-compose --profile core --profile insights up -d

# View status
docker-compose ps
docker stats
```

## Redis Specific Configuration

Redis has a maxmemory policy to prevent unbounded growth:

```bash
# In docker-compose.yml
command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

Options:
- `allkeys-lru`: Evict least recently used keys
- `volatile-lru`: Evict LRU keys with expiration set
- `allkeys-lfu`: Evict least frequently used keys

## PostgreSQL Specific Configuration

PostgreSQL memory settings are configured via environment variables:

```yaml
POSTGRES_SHARED_BUFFERS: 512MB
POSTGRES_WORK_MEM: 64MB
POSTGRES_MAINTENANCE_WORK_MEM: 128MB
```

These ensure PostgreSQL doesn't exceed the container's memory limits.

## Prometheus Retention

Configure retention in `prometheus/prometheus.yml`:

```yaml
global:
  retention: 15d           # Keep 15 days of data
  retention_size: 1GB      # Or max 1GB
```

## Preventing Image Growth

### Use .dockerignore
Created `.dockerignore` to prevent unnecessary files in images:
- Documentation files
- Tests
- Development tools
- Logs and temporary files

### Multi-stage Builds
For Python services:
```dockerfile
# Build stage
FROM python:3.11-slim as builder
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
```

### Alpine Images
Use Alpine-based images where possible (PostgreSQL, Redis already using Alpine):
- Smaller base image (~5MB vs ~100MB)
- Faster pull times
- Lower attack surface

## Monitoring Commands Cheat Sheet

```bash
# View all resource usage
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Check Docker disk usage
docker system df

# Find largest images
docker images --format "{{.Repository}}:{{.Tag}}\t{{.Size}}" | sort -k 2 -h | tail -10

# Find largest volumes
docker volume ls -q | xargs docker volume inspect --format '{{.Name}}: {{.Mountpoint}}' | xargs -I {} sh -c 'du -sh {}'

# Container log sizes
docker ps -q | xargs -I {} sh -c 'docker inspect --format="{{.Name}}: {{.LogPath}}" {} | xargs ls -lh'

# Total size of all containers
docker ps -a --size

# Cleanup unused resources
docker system prune -a -f
```

## Recommendations

1. **Development:**
   - Use minimal resource limits
   - Run cleanup weekly
   - Monitor disk space

2. **Production:**
   - Increase limits by 50-100%
   - Automated daily backups
   - Automated weekly cleanup
   - Real-time monitoring with alerts

3. **Cost Optimization:**
   - Remove unused services from profiles
   - Use smallest necessary limits
   - Aggressive cleanup policies
