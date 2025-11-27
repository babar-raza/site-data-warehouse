# Docker Optimization Implementation Guide
**Enterprise-Grade Docker Setup for GSC Warehouse**

Version: 1.0.0
Date: 2025-11-23
Status: Implementation Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Implementation Steps](#implementation-steps)
4. [Testing & Validation](#testing--validation)
5. [Rollback Plan](#rollback-plan)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)

---

## Overview

This guide walks through implementing the enterprise-grade Docker optimization for the GSC Warehouse project. The implementation provides:

- **70-98% faster builds** through split requirements and BuildKit caching
- **75-80% smaller images** via multi-stage builds
- **Hot reload in development** for rapid iteration
- **Production-ready deployment** with security hardening
- **CI/CD automation** with GitHub Actions

### What's Been Created

```
site-data-warehouse/
├── requirements/                    # Split requirements files
│   ├── base.txt                    # Core dependencies
│   ├── ingestors.txt               # GSC/GA4 ingestion
│   ├── insights.txt                # ML/AI packages
│   ├── api.txt                     # FastAPI services
│   ├── celery.txt                  # Async task processing
│   ├── metrics.txt                 # Prometheus metrics
│   ├── scheduler.txt               # APScheduler
│   ├── dev.txt                     # Development tools
│   └── all.txt                     # Complete set
│
├── compose/dockerfiles/
│   ├── Dockerfile.base             # Shared base image
│   ├── Dockerfile.*.new            # New optimized Dockerfiles
│   └── (old Dockerfiles preserved)
│
├── docker-compose.dev.yml          # Development overrides
├── docker-compose.prod.yml         # Production configuration
│
├── scripts/
│   ├── build-images.bat            # Windows build script
│   └── build-images.sh             # Linux build script
│
├── .github/workflows/
│   └── docker-build.yml            # CI/CD pipeline
│
├── .dockerignore                    # Optimized build context
└── .env.production.template        # Production env template
```

---

## Prerequisites

### System Requirements

**Development**:
- Docker Desktop 20.10+ with BuildKit enabled
- Docker Compose v2.0+
- 16GB+ RAM (for building ML images)
- 50GB+ free disk space

**Production**:
- Docker Engine 20.10+
- Docker Compose v2.0+ or Kubernetes 1.21+
- Container registry access (GitHub Container Registry, DockerHub, etc.)

### Enable BuildKit

**Windows (PowerShell)**:
```powershell
[System.Environment]::SetEnvironmentVariable('DOCKER_BUILDKIT', '1', 'User')
[System.Environment]::SetEnvironmentVariable('COMPOSE_DOCKER_CLI_BUILD', '1', 'User')
```

**Linux/macOS**:
```bash
echo 'export DOCKER_BUILDKIT=1' >> ~/.bashrc
echo 'export COMPOSE_DOCKER_CLI_BUILD=1' >> ~/.bashrc
source ~/.bashrc
```

**Verify**:
```bash
docker buildx version
# Should show: github.com/docker/buildx v0.10.0+
```

---

## Implementation Steps

### Phase 1: Backup Current Setup (15 minutes)

1. **Backup current configuration**:
```bash
# Windows
copy docker-compose.yml docker-compose.yml.backup
xcopy /E /I compose\dockerfiles compose\dockerfiles.backup

# Linux/macOS
cp docker-compose.yml docker-compose.yml.backup
cp -r compose/dockerfiles compose/dockerfiles.backup
```

2. **Save current images** (optional, for quick rollback):
```bash
docker compose build
docker save $(docker images 'gsc_*' -q) -o gsc-images-backup.tar
```

3. **Document current state**:
```bash
docker images gsc_* > current-images.txt
docker ps -a > current-containers.txt
```

### Phase 2: Migrate Dockerfiles (30 minutes)

1. **Rename old Dockerfiles**:
```bash
# Windows
for /f %i in ('dir /b compose\dockerfiles\Dockerfile.*') do @ren "compose\dockerfiles\%i" "%i.old"

# Linux/macOS
cd compose/dockerfiles
for f in Dockerfile.*; do
    if [[ ! "$f" =~ \.new$ ]] && [[ ! "$f" =~ \.old$ ]]; then
        mv "$f" "$f.old"
    fi
done
cd ../..
```

2. **Activate new Dockerfiles**:
```bash
# Windows
for /f %i in ('dir /b compose\dockerfiles\Dockerfile.*.new') do @ren "compose\dockerfiles\%i" "%~ni"

# Linux/macOS
cd compose/dockerfiles
for f in Dockerfile.*.new; do
    mv "$f" "${f%.new}"
done
cd ../..
```

3. **Verify**:
```bash
ls compose/dockerfiles/Dockerfile.*
# Should show: Dockerfile.api_ingestor, Dockerfile.ga4_ingestor, etc. (without .new)
```

### Phase 3: Build Base Image (10 minutes)

1. **Build the shared base image**:
```bash
# Windows
scripts\build-images.bat dev

# Linux/macOS
./scripts/build-images.sh dev
```

2. **Verify base image**:
```bash
docker images gsc-base
# Should show gsc-base:latest
```

3. **Check base image size**:
```bash
docker images gsc-base --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
# Should be ~300-400MB
```

### Phase 4: Build Service Images (20-30 minutes first time)

1. **Build all services**:
```bash
# Development
docker compose -f docker-compose.yml -f docker-compose.dev.yml build

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
```

2. **Verify all images**:
```bash
docker images gsc-* --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"
```

3. **Expected image sizes**:
```
REPOSITORY              SIZE
gsc-base               ~350MB
gsc-api-ingestor       ~400MB
gsc-ga4-ingestor       ~400MB
gsc-scheduler          ~450MB
gsc-transformer        ~350MB
gsc-insights-engine    ~1.2GB  (ML models)
gsc-insights-api       ~400MB
gsc-mcp                ~400MB
gsc-metrics            ~380MB
gsc-celery             ~2.5GB  (full ML + Playwright)
```

### Phase 5: Test Development Environment (15 minutes)

1. **Stop current containers**:
```bash
docker compose down
```

2. **Start development environment**:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up
```

3. **Verify services**:
```bash
# Check all containers are running
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps

# Check health
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps --filter health=healthy

# Check logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail=50
```

4. **Test hot reload**:
   - Modify a Python file in `ingestors/api/`
   - Check logs for auto-restart message
   - Verify changes without rebuild

5. **Test database connectivity**:
```bash
docker compose exec warehouse psql -U gsc_user -d gsc_db -c "SELECT version();"
```

### Phase 6: Production Configuration (30 minutes)

1. **Create production environment file**:
```bash
cp .env.production.template .env.production
```

2. **Edit `.env.production`** with actual values:
   - Database passwords
   - API keys
   - Registry information
   - Resource limits

3. **Configure secrets** (recommended for production):
```bash
# Create secrets directory
mkdir -p secrets
chmod 700 secrets

# Place service account JSON
cp /path/to/gsc-service-account.json secrets/gsc_sa.json
chmod 600 secrets/gsc_sa.json
```

4. **Test production build locally**:
```bash
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml build
```

### Phase 7: CI/CD Setup (if using GitHub) (20 minutes)

1. **Configure GitHub Container Registry**:
   - Go to GitHub repository → Settings → Actions
   - Enable "Read and write permissions" for GITHUB_TOKEN
   - No additional secrets needed (uses GITHUB_TOKEN)

2. **Verify workflow**:
```bash
git add .github/workflows/docker-build.yml
git commit -m "Add Docker CI/CD workflow"
git push
```

3. **Monitor first build**:
   - Go to Actions tab in GitHub
   - Watch "Build and Push Docker Images" workflow
   - First build will take 15-20 minutes (builds cache)
   - Subsequent builds: 3-5 minutes

4. **Verify images in registry**:
   - Go to repository → Packages
   - Should see: gsc-base, gsc-api-ingestor, etc.

---

## Testing & Validation

### Build Performance Test

1. **Measure initial build time**:
```bash
time docker compose -f docker-compose.yml -f docker-compose.dev.yml build
# Record time (expect 4-6 minutes)
```

2. **Test rebuild after code change**:
```bash
# Make small change to Python file
echo "# test change" >> ingestors/api/gsc_api_ingestor.py

# Rebuild
time docker compose -f docker-compose.yml -f docker-compose.dev.yml build api_ingestor
# Record time (expect 10-30 seconds)
```

3. **Test full rebuild with cache**:
```bash
time docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache
# Record time (expect 8-10 minutes, still faster than old 15-20 min)
```

### Functional Testing

1. **Test ingestion**:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api_ingestor python -c "from ingestors.api import gsc_api_ingestor; print('Import successful')"
```

2. **Test insights generation**:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm insights_engine python -m insights_core.cli refresh-insights
```

3. **Test API endpoint**:
```bash
curl http://localhost:8000/api/health
# Should return: {"status":"healthy","database":"connected",...}
```

4. **Test Celery worker**:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec celery_worker celery -A services.tasks inspect ping
# Should return: pong
```

### Security Validation

1. **Verify non-root user**:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm insights_api whoami
# Should return: appuser (not root)
```

2. **Check for vulnerabilities** (requires Trivy):
```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image gsc-insights-api:latest
```

3. **Verify secrets not in image**:
```bash
docker run --rm gsc-api-ingestor:latest ls /secrets/
# Should fail (directory shouldn't exist in image)
```

---

## Rollback Plan

### If Issues Arise During Implementation

**Quick Rollback (5 minutes)**:

1. **Restore old Dockerfiles**:
```bash
# Windows
for /f %i in ('dir /b compose\dockerfiles\Dockerfile.*.old') do @ren "compose\dockerfiles\%i" "%~ni"

# Linux/macOS
cd compose/dockerfiles && \
for f in Dockerfile.*.old; do mv "$f" "${f%.old}"; done && \
cd ../..
```

2. **Restore old docker-compose.yml**:
```bash
cp docker-compose.yml.backup docker-compose.yml
```

3. **Rebuild with old setup**:
```bash
docker compose build
docker compose up -d
```

**If saved image backup**:
```bash
docker load -i gsc-images-backup.tar
docker compose up -d
```

### Partial Rollback (Service-Specific)

If only one service has issues:

```bash
# Use old Dockerfile for that service only
cp compose/dockerfiles/Dockerfile.api_ingestor.old compose/dockerfiles/Dockerfile.api_ingestor

# Rebuild just that service
docker compose build api_ingestor
docker compose up -d api_ingestor
```

---

## Monitoring & Maintenance

### Build Cache Management

**View cache usage**:
```bash
docker buildx du
docker system df
```

**Clean build cache** (if running low on space):
```bash
# Remove old cache (keeps recent)
docker buildx prune --keep-storage 10GB

# Remove all cache (nuclear option)
docker buildx prune -af
```

### Image Registry Maintenance

**Cleanup old images from registry**:
```bash
# Via GitHub CLI
gh api -X DELETE /user/packages/container/gsc-api-ingestor/versions/OLD_VERSION_ID
```

**Tag management**:
```bash
# Tag for specific version
docker tag gsc-api-ingestor:latest ghcr.io/your-org/gsc-api-ingestor:v1.2.3
docker push ghcr.io/your-org/gsc-api-ingestor:v1.2.3
```

### Performance Monitoring

**Track build times**:
```bash
# Add to CI/CD or local builds
echo "$(date),$(docker compose build --progress=plain 2>&1 | grep 'Total time' | awk '{print $3}')" >> build-metrics.csv
```

**Monitor image sizes**:
```bash
docker images gsc-* --format "{{.Repository}},{{.Tag}},{{.Size}}" > image-sizes-$(date +%Y%m%d).csv
```

---

## Troubleshooting

### Common Issues

#### Issue: BuildKit not enabled

**Symptoms**:
- Builds don't use cache mounts
- `syntax=docker/dockerfile:1.4` error

**Solution**:
```bash
# Check if enabled
docker buildx version

# Enable BuildKit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

#### Issue: "permission denied" errors

**Symptoms**:
- Container can't access mounted volumes
- Permission errors in logs

**Solution**:
```bash
# Windows: Ensure Docker Desktop has file sharing enabled
# Settings → Resources → File Sharing

# Linux: Fix permissions
sudo chown -R $USER:$USER .
chmod -R 755 .
```

#### Issue: Out of disk space during build

**Symptoms**:
- Build fails with "no space left on device"

**Solution**:
```bash
# Clean up
docker system prune -af
docker volume prune -f

# Check space
docker system df

# If still needed, increase Docker Desktop disk limit
# Settings → Resources → Disk image size
```

#### Issue: Base image build fails

**Symptoms**:
- Can't find requirements/base.txt
- pip install errors

**Solution**:
```bash
# Verify requirements files exist
ls requirements/

# Ensure .dockerignore doesn't exclude requirements/
grep -v "^#" .dockerignore | grep requirements

# If excluded, update .dockerignore:
echo "!requirements/" >> .dockerignore
```

#### Issue: Service image references old base

**Symptoms**:
- Build uses cached old base instead of new one

**Solution**:
```bash
# Force rebuild of base
docker build --no-cache --target base-runtime -t gsc-base:latest -f compose/dockerfiles/Dockerfile.base .

# Then rebuild services
docker compose build --no-cache
```

#### Issue: Hot reload not working in development

**Symptoms**:
- Code changes don't trigger restart
- Have to rebuild manually

**Solution**:
```bash
# Verify using development target
docker compose -f docker-compose.yml -f docker-compose.dev.yml config | grep target
# Should show: target: development

# Check volume mounts
docker compose -f docker-compose.yml -f docker-compose.dev.yml config | grep volumes -A 5

# Restart specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart api_ingestor
```

#### Issue: CI/CD builds failing

**Symptoms**:
- GitHub Actions workflow errors
- Can't push to registry

**Solution**:
```bash
# Check permissions
# GitHub → Settings → Actions → Workflow permissions
# Ensure "Read and write permissions" is selected

# Verify registry access locally
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_ACTOR --password-stdin

# Test build locally with same args as CI
docker buildx build \
  --platform linux/amd64 \
  --cache-from type=registry,ref=ghcr.io/your-org/gsc-base:buildcache \
  --cache-to type=registry,ref=ghcr.io/your-org/gsc-base:buildcache,mode=max \
  -t gsc-base:test \
  -f compose/dockerfiles/Dockerfile.base .
```

### Getting Help

**Collect diagnostic information**:
```bash
# Create support bundle
docker info > docker-info.txt
docker version > docker-version.txt
docker compose version > compose-version.txt
docker images > docker-images.txt
docker ps -a > docker-containers.txt
docker compose -f docker-compose.yml -f docker-compose.dev.yml config > compose-config.txt

# Compress
tar -czf docker-diagnostics-$(date +%Y%m%d).tar.gz docker-*.txt
```

**Check logs**:
```bash
# Service-specific logs
docker compose logs service_name

# Follow logs in real-time
docker compose logs -f --tail=100

# Build logs with verbose output
docker compose build --progress=plain service_name 2>&1 | tee build.log
```

---

## Success Criteria

Implementation is successful when:

- ✅ Base image builds in < 3 minutes
- ✅ Service images build in < 5 minutes (parallel)
- ✅ Code changes rebuild in < 30 seconds
- ✅ Image sizes reduced by 60-80%
- ✅ Hot reload works in development
- ✅ All health checks passing
- ✅ CI/CD pipeline green
- ✅ Production deployment successful

---

## Next Steps After Implementation

1. **Update Documentation**
   - Update README.md with new build commands
   - Document production deployment process
   - Create runbooks for operations

2. **Train Team**
   - Share this guide with developers
   - Run through development workflow
   - Practice rollback procedures

3. **Optimize Further**
   - Monitor build times over time
   - Identify bottlenecks
   - Consider additional caching strategies

4. **Production Deployment**
   - Deploy to staging environment
   - Run load tests
   - Deploy to production with blue/green strategy

---

**Document Version**: 1.0.0
**Last Updated**: 2025-11-23
**Maintained By**: DevOps Team
**Questions?**: Create an issue in the repository
