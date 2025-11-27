# Rollback Automation - Quick Start Guide

## Overview

Automated health monitoring and rollback system that continuously monitors service health and automatically rolls back to previous versions when failures exceed thresholds.

## Key Features

- **30-second health check intervals** (configurable)
- **3 consecutive failure threshold** before rollback (configurable)
- **Automatic Docker image rollback** to previous versions
- **Comprehensive logging** of all actions
- **Graceful shutdown** on SIGINT/SIGTERM
- **Multi-service monitoring**: HTTP, PostgreSQL, Docker containers

## Quick Start

### 1. Basic Usage (Default Settings)

```bash
# Start monitoring with defaults
python scripts/rollback_automation.py

# With custom log file
python scripts/rollback_automation.py --log-file /var/log/rollback.log
```

### 2. Dry Run Mode (Recommended First)

```bash
# Test without actual rollbacks
python scripts/rollback_automation.py --dry-run --verbose
```

### 3. Custom Configuration

```bash
# Use configuration file
python scripts/rollback_automation.py \
  --config scripts/rollback_automation_config.example.json

# Override specific settings
python scripts/rollback_automation.py \
  --check-interval 60 \
  --failure-threshold 5 \
  --timeout 15
```

## Default Monitoring Configuration

### Hard Rules (As Per Requirements)

- **Check Interval**: 30 seconds
- **Failure Threshold**: 3 consecutive failures
- **Timeout**: 10 seconds per check
- **Monitored Services**:
  - insights_api (HTTP: 8000/api/health)
  - mcp (HTTP: 8001/health)
  - metrics_exporter (HTTP: 8002/metrics)
  - warehouse (PostgreSQL)
  - scheduler (Docker)
  - api_ingestor (Docker)
  - ga4_ingestor (Docker)

### Service Criticality

**Critical Services** (trigger rollback):
- insights_api
- mcp
- warehouse
- scheduler
- api_ingestor
- ga4_ingestor

**Non-Critical Services** (log only):
- metrics_exporter
- grafana
- prometheus

## How It Works

### 1. Health Check Cycle

Every 30 seconds:
1. Check all endpoints concurrently
2. Update failure counters
3. Log results
4. Trigger rollback if threshold exceeded

### 2. Failure Detection

```
Check 1: Failed → Count: 1 → Log: INFO
Check 2: Failed → Count: 2 → Log: WARNING
Check 3: Failed → Count: 3 → Log: ERROR + TRIGGER ROLLBACK
```

### 3. Rollback Process

When threshold exceeded:
1. **Backup**: Tag current image with timestamp
2. **Stop**: Gracefully stop service
3. **Remove**: Remove failed container
4. **Rollback**: Start with previous image
5. **Monitor**: Continue health checks
6. **Reset**: Reset failure counter on success

## Monitoring Logs

### Real-Time Monitoring

```bash
# Follow logs in real-time
tail -f rollback_automation_YYYYMMDD.log

# Watch for critical events
tail -f rollback_automation_YYYYMMDD.log | grep -E "CRITICAL|ERROR"
```

### Log Format

```
2025-11-27 10:00:00 - INFO - Starting health monitoring loop...
2025-11-27 10:00:30 - INFO - insights_api: Failed - Connection refused
2025-11-27 10:01:00 - WARNING - insights_api: WARNING - 2 consecutive failures
2025-11-27 10:01:30 - ERROR - insights_api: CRITICAL - 3 consecutive failures
2025-11-27 10:01:30 - CRITICAL - Services requiring rollback: insights_api
2025-11-27 10:01:35 - INFO - Successfully rolled back insights_api
```

## Rollback History

### Location

- `rollback_history_YYYYMMDD_HHMMSS.json`

### Format

```json
[
  {
    "timestamp": "2025-11-27T10:01:35.123456",
    "service_name": "insights_api",
    "from_version": "site-data-warehouse-insights_api:latest",
    "to_version": "site-data-warehouse-insights_api:backup_20251127_100000",
    "reason": "Health check failures exceeded threshold (3 consecutive failures)",
    "success": true,
    "details": {"method": "docker_compose"}
  }
]
```

## Command Reference

### Basic Commands

```bash
# Start monitoring
python scripts/rollback_automation.py

# Dry run (no actual rollbacks)
python scripts/rollback_automation.py --dry-run

# Verbose logging
python scripts/rollback_automation.py --verbose

# Custom interval (60 seconds)
python scripts/rollback_automation.py --check-interval 60

# Higher threshold (5 failures)
python scripts/rollback_automation.py --failure-threshold 5

# Stop monitoring (graceful)
Ctrl+C or SIGTERM
```

### Testing Commands

```bash
# Run test suite
python scripts/test_rollback_automation.py

# Syntax check
python -m py_compile scripts/rollback_automation.py

# Help
python scripts/rollback_automation.py --help
```

## Production Deployment

### As Background Process

```bash
# Start in background with nohup
nohup python scripts/rollback_automation.py \
  --log-file /var/log/rollback_automation.log \
  > /dev/null 2>&1 &

# Save PID
echo $! > /var/run/rollback_automation.pid

# Stop
kill $(cat /var/run/rollback_automation.pid)
```

### As Systemd Service

Create `/etc/systemd/system/rollback-automation.service`:

```ini
[Unit]
Description=Rollback Automation Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=/path/to/site-data-warehouse
ExecStart=/usr/bin/python3 scripts/rollback_automation.py \
  --log-file /var/log/rollback_automation.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable rollback-automation
sudo systemctl start rollback-automation
sudo systemctl status rollback-automation
```

## Environment Variables

```bash
# Required
export WAREHOUSE_DSN="postgresql://user:pass@host:5432/db"

# Optional (override defaults)
export BASE_URL="http://localhost"
export CHECK_INTERVAL=30
export FAILURE_THRESHOLD=3
export TIMEOUT=10
```

## Troubleshooting

### Issue: Services keep rolling back

**Solution**: Increase threshold or check interval
```bash
python scripts/rollback_automation.py --failure-threshold 5 --check-interval 60
```

### Issue: No previous image found

**Solution**: Tag images before deployment
```bash
docker tag service:latest service:backup_$(date +%Y%m%d)
```

### Issue: Permission denied

**Solution**: Add user to docker group
```bash
sudo usermod -aG docker $USER
```

### Issue: Module not found

**Solution**: Install dependencies
```bash
pip install asyncpg httpx
```

## Best Practices

1. **Always test in dry-run mode first**
   ```bash
   python scripts/rollback_automation.py --dry-run --verbose
   ```

2. **Start with lenient thresholds**
   - Development: 10 failures
   - Staging: 5 failures
   - Production: 3 failures

3. **Monitor logs regularly**
   ```bash
   tail -f rollback_automation_*.log
   ```

4. **Tag images before deployment**
   ```bash
   docker tag service:latest service:$(date +%Y%m%d_%H%M%S)
   ```

5. **Set up log rotation**
   ```bash
   # /etc/logrotate.d/rollback-automation
   /var/log/rollback_automation.log {
       daily
       rotate 7
       compress
   }
   ```

## Integration

### With CI/CD Pipeline

```yaml
# Example: GitHub Actions
deploy:
  steps:
    - name: Tag Current Image
      run: docker tag app:latest app:backup_${{ github.sha }}

    - name: Deploy New Version
      run: docker-compose up -d

    - name: Start Rollback Monitor
      run: |
        python scripts/rollback_automation.py \
          --failure-threshold 3 \
          --timeout 60 &
```

### With Monitoring Tools

```bash
# Export metrics to file for Prometheus scraping
python scripts/rollback_automation.py --metrics-export /var/metrics/rollback.prom
```

## Files Generated

- `rollback_automation_YYYYMMDD.log` - Daily log file
- `rollback_history_YYYYMMDD_HHMMSS.json` - Rollback history on shutdown
- Docker backup images: `service:backup_YYYYMMDD_HHMMSS`

## Support

See full documentation: `scripts/README_rollback_automation.md`

## Summary

The rollback automation script provides:
- **Continuous monitoring** every 30 seconds
- **Automatic rollback** after 3 consecutive failures
- **Comprehensive logging** of all actions
- **Graceful shutdown** handling
- **Zero-downtime recovery** with Docker image rollback

Perfect for production environments requiring automatic failure recovery.
