# Scripts Directory

This directory contains deployment, cleanup, and maintenance scripts for the Docker environment.

## Deployment Scripts

### `docker-deploy-limited.sh` (Linux/Mac)
Automated deployment script with resource limits.

**Usage:**
```bash
# Deploy core services
./docker-deploy-limited.sh core

# Deploy multiple profiles
./docker-deploy-limited.sh "core insights api"

# Rebuild and deploy
./docker-deploy-limited.sh core rebuild
```

**Features:**
- Stops existing containers
- Optional image cleanup
- Parallel image building
- Profile-based deployment
- Resource usage reporting

### `QUICK_DEPLOY.bat` (Windows)
Quick deployment script for Windows environments.

**Usage:**
```batch
REM Deploy core
scripts\QUICK_DEPLOY.bat core

REM Deploy with insights
scripts\QUICK_DEPLOY.bat "core insights"
```

**Features:**
- Docker status check
- Interactive cleanup option
- Parallel builds
- Status reporting
- Resource monitoring

## Cleanup Scripts

### `docker-cleanup.sh` (Linux/Mac)
Comprehensive cleanup script for Docker resources.

**Usage:**
```bash
./docker-cleanup.sh
```

**Removes:**
- Stopped containers
- Dangling images
- Unused volumes (with confirmation)
- Old build cache (>24h)
- Unused networks

**Options:**
- Interactive volume cleanup
- Aggressive cleanup mode (removes ALL unused data)

### `docker-cleanup.bat` (Windows)
Windows version of the cleanup script.

**Usage:**
```batch
scripts\docker-cleanup.bat
```

**Features:**
- Same cleanup capabilities as Linux version
- Docker status verification
- Interactive confirmations
- Disk usage reporting

## Utility Scripts

### `wait-for-services.sh` (Linux/Mac)
Wait for all critical services to be healthy before proceeding with deployments or tests.

**Usage:**
```bash
# Wait with default timeout (120s)
./wait-for-services.sh

# Wait with custom timeout
./wait-for-services.sh --timeout 60

# Wait with verbose output
./wait-for-services.sh --verbose --timeout 180
```

**Features:**
- Checks PostgreSQL, Redis, API, Grafana, and Prometheus
- Configurable timeout (default: 120 seconds)
- Verbose output mode for debugging
- Health check endpoint validation
- Exit code 0 on success, 1 on timeout
- Environment variable support for host/port configuration

**Exit Codes:**
- `0`: All services healthy
- `1`: Timeout reached or service check failed

### `wait-for-services.bat` (Windows)
Windows version of the service wait script.

**Usage:**
```batch
REM Wait with default timeout (120s)
scripts\wait-for-services.bat

REM Wait with custom timeout
scripts\wait-for-services.bat --timeout 60

REM Wait with verbose output
scripts\wait-for-services.bat --verbose --timeout 180
```

**Features:**
- Same functionality as Linux/Mac version
- PowerShell fallback for HTTP checks
- Native Windows batch scripting
- Color-coded status output

### `add-logging-to-compose.py`
Python script to add logging configuration to all services in docker-compose.yml.

**Usage:**
```bash
python add-logging-to-compose.py
```

**Features:**
- Adds log rotation to all services
- Adds tmpfs mounts
- Creates backup of original file
- Automatic size configuration

### `add-logging-manual.sh`
Helper script to identify services needing logging configuration.

**Usage:**
```bash
./add-logging-manual.sh
```

## Operational Scripts

### `sync_gsc_to_serp.py`
Syncs Google Search Console data to SERP tracking tables.

**Usage:**
```bash
python sync_gsc_to_serp.py
```

### `test_serpstack_api.py`
Tests SerpStack API connectivity and configuration.

**Usage:**
```bash
python test_serpstack_api.py
```

## Setup Scripts

Located in [`setup/`](setup/) directory:
- Database initialization scripts
- Schema creation scripts
- Initial data loading scripts

## Operations Scripts

Located in [`operations/`](operations/) directory:
- Backup and restore scripts
- Health check scripts
- Manual collection scripts
- Deployment scripts

## Making Scripts Executable

### Linux/Mac
```bash
chmod +x scripts/*.sh
chmod +x scripts/operations/*.sh
chmod +x scripts/setup/*.sh
```

### Windows
Scripts with `.bat` extension are automatically executable.
For `.sh` scripts, use Git Bash or WSL.

## Automation

### Linux/Mac Cron
```bash
# Edit crontab
crontab -e

# Add weekly cleanup (Sunday 2 AM)
0 2 * * 0 /path/to/scripts/docker-cleanup.sh

# Add daily health check
0 6 * * * /path/to/scripts/operations/health-check.sh
```

### Windows Task Scheduler
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., Weekly, Sunday, 2:00 AM)
4. Action: Start a program
5. Program: `C:\path\to\scripts\docker-cleanup.bat`

## Best Practices

1. **Run cleanup weekly** to prevent disk space issues
2. **Test scripts** in development before production use
3. **Review logs** after automated runs
4. **Backup volumes** before aggressive cleanup
5. **Monitor resource usage** after deployments
6. **Keep scripts updated** with docker-compose.yml changes

## Troubleshooting

### Permission Denied (Linux/Mac)
```bash
chmod +x script-name.sh
```

### Docker Not Running
```bash
# Check status
docker ps

# Start Docker
# Linux: sudo systemctl start docker
# Mac/Windows: Start Docker Desktop
```

### Script Hangs
- Check for interactive prompts
- Run with `-x` flag for debugging: `bash -x script.sh`
- Check Docker daemon logs

### Cleanup Removes Too Much
- Review confirmation prompts carefully
- Use selective cleanup instead of aggressive
- Keep recent backups

## Directory Structure

```
scripts/
├── README.md                    # This file
├── wait-for-services.sh         # Unix service wait script
├── wait-for-services.bat        # Windows service wait script
├── docker-deploy-limited.sh     # Linux/Mac deployment
├── docker-cleanup.sh            # Linux/Mac cleanup
├── docker-cleanup.bat           # Windows cleanup
├── add-logging-to-compose.py    # Add logging config
├── add-logging-manual.sh        # Logging helper
├── sync_gsc_to_serp.py         # GSC sync utility
├── test_serpstack_api.py       # API test utility
├── deploy.sh                    # Legacy deploy script
├── operations/                  # Operational scripts
│   ├── backup.sh/.bat          # Backup scripts
│   ├── restore.sh/.bat         # Restore scripts
│   ├── health-check.sh/.bat    # Health checks
│   ├── cleanup.sh/.bat         # Cleanup variants
│   └── ...
└── setup/                       # Setup scripts
    └── ...
```

## Additional Resources

- **Deployment Guide**: [`../docs/deployment/DEPLOYMENT_WITH_LIMITS.md`](../docs/deployment/DEPLOYMENT_WITH_LIMITS.md)
- **Resource Limits**: [`../docs/deployment/DOCKER_RESOURCE_LIMITS.md`](../docs/deployment/DOCKER_RESOURCE_LIMITS.md)
- **Summary**: [`../docs/deployment/DOCKER_DEPLOYMENT_SUMMARY.md`](../docs/deployment/DOCKER_DEPLOYMENT_SUMMARY.md)
- **Docker Compose**: [`../docker-compose.yml`](../docker-compose.yml)

## Support

For issues with scripts:
1. Check script permissions
2. Verify Docker is running
3. Review error messages
4. Check logs: `docker-compose logs`
5. Consult troubleshooting guides in main documentation
