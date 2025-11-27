# Testing Docker Optimization on Localhost

## Current Status

✅ BuildKit enabled
✅ New Dockerfiles activated
✅ Base image building...
⏳ Service images pending
⏳ Development environment pending

---

## What's Happening Now

The optimized Docker setup is being built for the first time:

1. **Base Image** (in progress): ~3-5 minutes
   - Installing core system dependencies
   - Installing base Python packages (psycopg2, pandas, sqlalchemy)
   - Creating non-root user (`appuser`)
   - Setting up security and health checks

2. **Service Images** (next): ~2-3 minutes
   - Will build in parallel
   - Each service installs only its required dependencies
   - Uses BuildKit cache mounts for speed

---

## Testing Checklist

### Step 1: Verify Build Completed

Once the build finishes, verify images were created:

```bash
docker images gsc-*
```

**Expected output**:
```
REPOSITORY              TAG       IMAGE ID       CREATED          SIZE
gsc-base                latest    abc123...      2 minutes ago    ~350MB
gsc-api-ingestor        latest    def456...      1 minute ago     ~400MB
gsc-ga4-ingestor        latest    ghi789...      1 minute ago     ~400MB
gsc-scheduler           latest    jkl012...      1 minute ago     ~450MB
gsc-insights-api        latest    mno345...      1 minute ago     ~400MB
# ... more services
```

### Step 2: Compare with Old Images (if you still have them)

```bash
docker images | grep -E "(REPOSITORY|gsc_)"
```

**Before optimization**: Each image was 2.5-3 GB
**After optimization**: Most images are 300-500 MB (except ML-heavy ones)
**Improvement**: ~75-85% size reduction

### Step 3: Test Development Environment

Start the core services in development mode:

```bash
# Windows
$env:DOCKER_BUILDKIT=1
$env:COMPOSE_DOCKER_CLI_BUILD=1
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up

# Linux/macOS
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up
```

**What to look for**:
- ✅ All containers start successfully
- ✅ Health checks pass (look for "healthy" status)
- ✅ No Python import errors
- ✅ Database connections successful

### Step 4: Test Hot Reload (Development Mode)

1. **Make a code change**:
```bash
# Open a Python file
# For example: ingestors/api/gsc_api_ingestor.py

# Add a comment or print statement at the top
echo "# Test change - $(date)" >> ingestors/api/gsc_api_ingestor.py
```

2. **Watch the logs**:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f api_ingestor
```

3. **Expected behavior**:
- Container detects file change within ~2 seconds
- Logs show: "Detected changes, restarting..."
- Service restarts automatically
- **NO REBUILD REQUIRED!** (This is the key improvement)

### Step 5: Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Expected: {"status":"healthy"}

# Metrics endpoint
curl http://localhost:8002/metrics

# Expected: Prometheus metrics output
```

### Step 6: Test Database Connectivity

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec warehouse psql -U gsc_user -d gsc_db -c "SELECT version();"
```

**Expected**: PostgreSQL version information

### Step 7: Test Rebuild Speed (The Big Test!)

This tests the main optimization - fast rebuilds:

```bash
# 1. Make a small code change
echo "# rebuild test" >> ingestors/api/gsc_api_ingestor.py

# 2. Time the rebuild
time docker compose -f docker-compose.yml -f docker-compose.dev.yml build api_ingestor
```

**Expected results**:
- **Old way**: 15-20 minutes
- **New way**: 10-30 seconds ⚡
- **Improvement**: 98% faster!

### Step 8: Test Service Functionality

**API Ingestor**:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api_ingestor python -c "from ingestors.api import gsc_api_ingestor; print('✓ Import successful')"
```

**Insights Engine**:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm insights_engine python -c "from insights_core.config import InsightsConfig; print('✓ Import successful')"
```

**Celery Worker** (if using intelligence profile):
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile intelligence exec celery_worker celery -A services.tasks inspect ping
```

---

## Performance Benchmarks

### Build Times

Measure and compare:

| Test | Command | Expected Time |
|------|---------|---------------|
| **First build (base)** | Build base image | 3-5 min |
| **First build (all)** | Build all services | 4-6 min |
| **Rebuild (code change)** | Rebuild one service | **10-30 sec** |
| **Rebuild (no cache)** | Rebuild with --no-cache | 8-10 min |

### Image Sizes

Run and record:

```bash
docker images gsc-* --format "table {{.Repository}}\t{{.Size}}" > image-sizes-after.txt
```

**Expected reductions**:
- api_ingestor: 2.5GB → 400MB (84%)
- insights_api: 2.5GB → 400MB (84%)
- insights_engine: 3.5GB → 1.2GB (66%)
- celery: 3.5GB → 2.5GB (29% - has full ML stack)

### Memory Usage

While services are running:

```bash
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"
```

---

## Troubleshooting

### Issue: "Base image not found"

```bash
# Check if base image exists
docker images gsc-base

# If missing, build it
docker build --target base-runtime -t gsc-base:latest -f compose/dockerfiles/Dockerfile.base .
```

### Issue: "Permission denied" errors

```bash
# Windows: Enable file sharing in Docker Desktop
# Settings → Resources → File Sharing

# Linux: Fix ownership
sudo chown -R $USER:$USER .
```

### Issue: Hot reload not working

```bash
# Verify you're using development compose file
docker compose -f docker-compose.yml -f docker-compose.dev.yml config | grep target

# Should show: target: development

# Restart service
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart api_ingestor
```

### Issue: Build fails with "out of space"

```bash
# Clean up old images and build cache
docker system prune -af
docker buildx prune -f

# Check available space
docker system df
```

### Issue: Services fail to start

```bash
# Check logs for specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs api_ingestor

# Check all health statuses
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps

# Restart specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart api_ingestor
```

---

## Success Criteria

Your optimization is working correctly if:

- ✅ Base image builds in < 5 minutes
- ✅ All service images build successfully
- ✅ Total first build time < 6 minutes
- ✅ Code changes rebuild in < 30 seconds
- ✅ Hot reload works (no rebuild needed)
- ✅ Image sizes reduced by 70-85%
- ✅ All health checks pass
- ✅ Services function correctly

---

## Next Steps After Successful Testing

1. **Clean up old images** (if satisfied):
```bash
docker images | grep "\.old" # List old images
docker rmi $(docker images -q -f "dangling=true") # Remove dangling
```

2. **Update your workflow**:
   - Use `docker-compose.dev.yml` for development
   - Use `docker-compose.prod.yml` for production
   - Use `scripts/build-images.sh` for consistent builds

3. **Configure production**:
```bash
cp .env.production.template .env.production
# Edit .env.production with real values
```

4. **Set up CI/CD** (optional):
   - GitHub Actions workflow already created
   - Will run automatically on push to main/develop
   - Builds and pushes to GitHub Container Registry

---

## Current Build Progress

Check the build progress with:

```bash
# See if build is still running
docker ps -a | grep -i build

# Check BuildKit cache usage
docker buildx du

# Monitor Docker events
docker events --since 5m
```

---

## Quick Reference Commands

### Development
```bash
# Build images
scripts/build-images.sh dev

# Start services
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up

# View logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# Stop services
docker compose down
```

### Production
```bash
# Build images
scripts/build-images.sh prod

# Start services
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml --profile core up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop services
docker compose -f docker-compose.prod.yml down
```

---

**Build started**: ~16:27 UTC
**Estimated completion**: ~16:32-16:35 UTC (4-6 min total)
**Status**: Check with `docker images gsc-*` to see completed images
