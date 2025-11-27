# Deployment Guide with Resource Limits

## Prerequisites

1. **Start Docker Desktop**
   - Ensure Docker Desktop is running
   - Check status: `docker ps`

2. **Verify Configuration**
   - Check `.env` file exists with credentials
   - Verify `secrets/` directory has credentials (if using GSC/GA4)

## Quick Deployment

### Option 1: Automated Script (Recommended)

```bash
# Deploy core services
./scripts/docker-deploy-limited.sh core

# Deploy with multiple profiles
./scripts/docker-deploy-limited.sh "core insights api intelligence"

# Rebuild and deploy
./scripts/docker-deploy-limited.sh core rebuild
```

### Option 2: Manual Deployment

```bash
# 1. Stop existing containers
docker-compose down

# 2. Clean up (optional)
./scripts/docker-cleanup.sh

# 3. Build images
docker-compose build --parallel

# 4. Deploy with profile
docker-compose --profile core up -d

# 5. Check status
docker-compose ps
docker stats --no-stream
```

## Step-by-Step Deployment

### Step 1: Pre-Deployment Cleanup

```bash
# Stop all running containers
docker-compose down --remove-orphans

# Remove old containers
docker container prune -f

# Remove unused images
docker image prune -f

# Check disk usage
docker system df
```

### Step 2: Configuration Review

```bash
# Verify environment variables
cat .env | grep -v "^#" | grep -v "^$"

# Check docker-compose.yml for resource limits
grep -A 5 "resources:" docker-compose.yml
```

### Step 3: Build Images

```bash
# Build all images
docker-compose build --parallel

# Or build specific service
docker-compose build warehouse
```

### Step 4: Deploy Services

#### Core Profile (Minimal)
```bash
docker-compose --profile core up -d
```

Services started:
- warehouse (PostgreSQL)
- startup_orchestrator
- api_ingestor
- ga4_ingestor
- transform

#### With Insights
```bash
docker-compose --profile core --profile insights up -d
```

Additional services:
- insights_engine
- scheduler

#### With API Layer
```bash
docker-compose --profile core --profile insights --profile api up -d
```

Additional services:
- insights_api
- mcp

#### Full Stack (All Profiles)
```bash
docker-compose --profile core --profile insights --profile api --profile intelligence up -d
```

**Note**: Prometheus, Grafana, and metrics_exporter are now always enabled and will start with any deployment

#### With Intelligence (Ollama)
```bash
docker-compose --profile core --profile insights --profile intelligence up -d
```

Additional services:
- ollama
- redis
- celery_worker

### Step 5: Verify Deployment

```bash
# Check container status
docker-compose ps

# Check health
docker-compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"

# View logs
docker-compose logs -f --tail=50

# Check resource usage
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

### Step 6: Test Services

```bash
# Test database
docker-compose exec warehouse psql -U ${POSTGRES_USER:-gsc_user} -d ${POSTGRES_DB:-gsc_db} -c "SELECT version();"

# Test Insights API (if running)
curl http://localhost:8000/api/health

# Test MCP Server (if running)
curl http://localhost:8001/health

# Test Grafana (if running)
curl http://localhost:3000/api/health

# Test Ollama (if running)
curl http://localhost:11434/api/version
```

## Resource Limits Applied

### Memory Limits
- **warehouse**: 2GB (reserved: 512MB)
- **ollama**: 8GB (reserved: 2GB)
- **celery_worker**: 2GB
- **insights_engine**: 1GB
- **scheduler**: 1GB
- **api_ingestor**: 512MB
- **grafana**: 512MB
- **redis**: 512MB (with maxmemory policy)
- **others**: 256-512MB

### CPU Limits
- **warehouse**: 2.0 cores (reserved: 0.5)
- **ollama**: 4.0 cores (reserved: 2.0)
- **celery_worker**: 2.0 cores
- **insights_engine**: 1.0 core
- **api_ingestor**: 1.0 core
- **others**: 0.25-1.0 cores

### Log Limits
All services (where configured):
- **max-size**: 10MB per log file
- **max-file**: 3 files
- **total per container**: 30MB max

### Tmpfs Mounts
- **warehouse**: 256MB /tmp
- **ollama**: 512MB /tmp
- **others**: 64-128MB /tmp

## Monitoring

### Real-time Monitoring
```bash
# Live stats (press Ctrl+C to exit)
docker stats

# One-time snapshot
docker stats --no-stream

# Specific service
docker stats gsc_warehouse
```

### Disk Usage
```bash
# Overall Docker usage
docker system df

# Detailed breakdown
docker system df -v

# Container sizes
docker ps -a --size
```

### Logs
```bash
# View all logs
docker-compose logs

# Specific service
docker-compose logs warehouse

# Follow logs
docker-compose logs -f --tail=100

# Log file sizes
docker ps -q | xargs -I {} sh -c 'echo -n "{}: "; docker inspect --format="{{.LogPath}}" {} | xargs ls -lh | awk "{print \$5}"'
```

## Cleanup

### Manual Cleanup
```bash
# Run cleanup script
./scripts/docker-cleanup.sh

# This will:
# - Stop all containers
# - Remove stopped containers
# - Remove dangling images
# - Optionally remove volumes
# - Remove old build cache
# - Remove unused networks
```

### Selective Cleanup
```bash
# Stop specific service
docker-compose stop insights_engine

# Remove specific service
docker-compose rm -f insights_engine

# Remove specific volume
docker volume rm site-data-warehouse_grafana_data

# Remove specific image
docker image rm gsc_insights_engine
```

### Emergency Cleanup
```bash
# Stop everything
docker-compose down --remove-orphans

# Nuclear option (removes EVERYTHING)
docker system prune -a --volumes -f
```

⚠️ **WARNING**: `docker system prune -a --volumes -f` removes ALL data including volumes!

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker-compose logs service_name

# Check container details
docker inspect gsc_service_name

# Check resource availability
docker stats --no-stream
```

### Out of Memory
```bash
# Check which container
docker stats --no-stream | sort -k 4 -h

# Increase memory in docker-compose.yml
# Edit the service:
deploy:
  resources:
    limits:
      memory: 4G  # Increase as needed
```

### Disk Space Full
```bash
# Find large images
docker images --format "{{.Repository}}:{{.Tag}}\t{{.Size}}" | sort -k 2 -h

# Find large volumes
docker volume ls -q | xargs docker volume inspect --format '{{.Name}}' | xargs -I {} sh -c 'du -sh /var/lib/docker/volumes/{}'

# Cleanup
./scripts/docker-cleanup.sh
```

### Service Unhealthy
```bash
# Check health status
docker-compose ps

# Check health check definition
docker inspect gsc_warehouse | grep -A 10 "Health"

# View health check logs
docker inspect gsc_warehouse --format='{{json .State.Health}}' | jq
```

### Build Errors
```bash
# Clean build cache
docker builder prune -f

# Rebuild from scratch
docker-compose build --no-cache service_name

# Check .dockerignore
cat .dockerignore
```

## Best Practices

1. **Always use profiles** to avoid starting unnecessary services
2. **Monitor resource usage** weekly with `docker stats`
3. **Run cleanup monthly** with `./scripts/docker-cleanup.sh`
4. **Backup volumes** before major updates
5. **Check logs regularly** for errors or warnings
6. **Adjust limits** based on actual usage patterns
7. **Use health checks** to ensure services are running correctly
8. **Set up alerts** for high resource usage in production

## Production Checklist

- [ ] Resource limits configured for all services
- [ ] Log rotation enabled (10MB max, 3 files)
- [ ] Health checks defined and passing
- [ ] Automated backups set up for volumes
- [ ] Monitoring dashboards configured (Grafana)
- [ ] Cleanup script in cron (weekly)
- [ ] Alerts configured for resource thresholds
- [ ] .env file secured (not in git)
- [ ] Secrets properly mounted (read-only)
- [ ] Network isolation configured
- [ ] Regular update schedule established

## Common Commands Reference

```bash
# Deployment
docker-compose --profile core up -d
docker-compose --profile core --profile insights up -d

# Status
docker-compose ps
docker stats --no-stream
docker system df

# Logs
docker-compose logs -f
docker-compose logs service_name --tail=100

# Stop/Start
docker-compose stop
docker-compose start
docker-compose restart service_name

# Cleanup
./scripts/docker-cleanup.sh
docker-compose down
docker system prune -f

# Rebuild
docker-compose build --no-cache
docker-compose up -d --build

# Execute commands
docker-compose exec warehouse psql -U gsc_user -d gsc_db
docker-compose exec redis redis-cli

# Scale (if supported)
docker-compose up -d --scale celery_worker=3
```

## Next Steps

After successful deployment:

1. **Verify all services are healthy:**
   ```bash
   docker-compose ps
   ```

2. **Check resource usage:**
   ```bash
   docker stats --no-stream
   ```

3. **Review logs for errors:**
   ```bash
   docker-compose logs | grep -i error
   ```

4. **Test API endpoints** (if deployed)

5. **Set up monitoring alerts**

6. **Configure automated backups**

7. **Schedule cleanup script**
