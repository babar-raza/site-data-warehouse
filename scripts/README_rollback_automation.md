# Rollback Automation Script

Automated health monitoring and rollback system for Docker services.

## Features

- **Continuous Health Monitoring**: Monitors HTTP endpoints, PostgreSQL, and Docker services
- **Automatic Rollback**: Triggers rollback to previous Docker image versions on failure
- **Configurable Thresholds**: Set failure thresholds and check intervals
- **Comprehensive Logging**: Logs all health checks and actions
- **Graceful Shutdown**: Handles SIGINT/SIGTERM signals properly
- **Dry Run Mode**: Test without performing actual rollbacks
- **Multi-Service Support**: Monitor multiple services concurrently
- **History Tracking**: Maintains history of rollbacks and health checks

## Requirements

```bash
pip install asyncpg httpx
```

## Quick Start

### Basic Usage

```bash
# Start monitoring with default settings
python scripts/rollback_automation.py

# Dry run mode (no actual rollbacks)
python scripts/rollback_automation.py --dry-run

# Custom check interval and threshold
python scripts/rollback_automation.py --check-interval 60 --failure-threshold 5
```

### With Configuration File

```bash
# Use custom configuration
python scripts/rollback_automation.py --config rollback_automation_config.json

# Custom config with verbose logging
python scripts/rollback_automation.py --config config.json --verbose
```

## Configuration

### Command Line Options

```
--config FILE              Path to configuration file (JSON)
--check-interval SECONDS   Health check interval (default: 30)
--failure-threshold COUNT  Consecutive failures before rollback (default: 3)
--timeout SECONDS         Health check timeout (default: 10)
--log-file PATH           Path to log file
--dry-run                 Test mode - no actual rollbacks
--verbose                 Enable verbose logging
```

### Configuration File Format

See `rollback_automation_config.example.json` for a complete example:

```json
{
  "health_check": {
    "failure_threshold": 3,
    "check_interval": 30,
    "timeout": 10,
    "warning_threshold": 2
  },
  "endpoints": [
    {
      "name": "insights_api",
      "url": "http://localhost:8000/api/health",
      "type": "http",
      "critical": true
    }
  ]
}
```

### Endpoint Types

1. **HTTP Endpoints**: Monitor REST API health endpoints
   ```json
   {
     "name": "insights_api",
     "url": "http://localhost:8000/api/health",
     "type": "http",
     "critical": true
   }
   ```

2. **PostgreSQL**: Monitor database connectivity
   ```json
   {
     "name": "warehouse",
     "url": "postgresql://user:pass@host:5432/db",
     "type": "postgres",
     "critical": true
   }
   ```

3. **Docker Services**: Monitor container health
   ```json
   {
     "name": "scheduler",
     "url": "",
     "type": "docker",
     "critical": true
   }
   ```

## How It Works

### Health Check Flow

1. **Concurrent Checks**: All endpoints checked in parallel every interval
2. **Failure Counting**: Track consecutive failures per service
3. **Threshold Detection**: Alert when failures exceed threshold
4. **Automatic Rollback**: Rollback critical services on threshold breach
5. **Recovery Monitoring**: Continue monitoring after rollback

### Rollback Process

When a service exceeds the failure threshold:

1. **Image Backup**: Current image tagged with timestamp
2. **Service Stop**: Gracefully stop the failing service
3. **Container Remove**: Remove the unhealthy container
4. **Image Rollback**: Identify previous stable image version
5. **Service Restart**: Start service with previous image
6. **Verification**: Continue monitoring to verify recovery

### Failure States

- **Healthy**: Service responding normally
- **Degraded**: Warning threshold reached (no action)
- **Unhealthy**: Failure threshold reached (trigger rollback)
- **Unknown**: Cannot determine status

## Environment Variables

```bash
# Database connection
export WAREHOUSE_DSN="postgresql://user:pass@host:5432/db"

# Service URLs (optional, has defaults)
export BASE_URL="http://localhost"

# Logging
export LOG_LEVEL="INFO"
```

## Usage Examples

### Production Deployment

```bash
# Run as background service with logging
nohup python scripts/rollback_automation.py \
  --check-interval 30 \
  --failure-threshold 3 \
  --log-file /var/log/rollback_automation.log \
  > /dev/null 2>&1 &
```

### Testing Configuration

```bash
# Test with dry run and verbose output
python scripts/rollback_automation.py \
  --config test_config.json \
  --dry-run \
  --verbose
```

### Quick Health Check

```bash
# Run one check cycle (set very short interval)
timeout 60 python scripts/rollback_automation.py \
  --check-interval 30 \
  --verbose
```

## Monitoring & Logs

### Log Output

The script generates detailed logs:

```
2025-11-27 10:00:00 - INFO - Starting health monitoring loop...
2025-11-27 10:00:00 - INFO - Check interval: 30s
2025-11-27 10:00:00 - INFO - Failure threshold: 3
2025-11-27 10:00:00 - INFO - Monitoring 8 endpoints
2025-11-27 10:00:05 - INFO - insights_api: Failed - Connection refused
2025-11-27 10:00:35 - WARNING - insights_api: WARNING - 2 consecutive failures
2025-11-27 10:01:05 - ERROR - insights_api: CRITICAL - 3 consecutive failures
2025-11-27 10:01:05 - CRITICAL - Services requiring rollback: insights_api
2025-11-27 10:01:05 - INFO - Initiating rollback for insights_api...
2025-11-27 10:01:10 - INFO - Successfully rolled back insights_api
```

### Log Files

- **Main Log**: `rollback_automation_YYYYMMDD.log`
- **Rollback History**: `rollback_history_YYYYMMDD_HHMMSS.json`

### Rollback History Format

```json
[
  {
    "timestamp": "2025-11-27T10:01:05.123456",
    "service_name": "insights_api",
    "from_version": "site-data-warehouse-insights_api:latest",
    "to_version": "site-data-warehouse-insights_api:backup_20251127_100000",
    "reason": "Health check failures exceeded threshold (3 consecutive failures)",
    "success": true,
    "details": {
      "method": "docker_compose"
    }
  }
]
```

## Integration

### Systemd Service

Create `/etc/systemd/system/rollback-automation.service`:

```ini
[Unit]
Description=Rollback Automation Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/site-data-warehouse
ExecStart=/usr/bin/python3 /path/to/scripts/rollback_automation.py \
  --config /path/to/config.json \
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

### Docker Compose Integration

Add to `docker-compose.yml`:

```yaml
rollback_automation:
  build:
    context: .
    dockerfile: compose/dockerfiles/Dockerfile.automation
  container_name: gsc_rollback_automation
  environment:
    WAREHOUSE_DSN: ${WAREHOUSE_DSN}
    CHECK_INTERVAL: 30
    FAILURE_THRESHOLD: 3
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - ./logs:/logs
  restart: unless-stopped
```

### Cron Job (Not Recommended for Continuous Monitoring)

```cron
# Check every 5 minutes
*/5 * * * * cd /path/to/repo && python3 scripts/rollback_automation.py --check-interval 30 --timeout 60
```

## Best Practices

### 1. Failure Thresholds

- **Development**: Use higher thresholds (5-10) to avoid false positives
- **Staging**: Use moderate thresholds (3-5)
- **Production**: Use strict thresholds (2-3) for critical services

### 2. Check Intervals

- **Critical Services**: 15-30 seconds
- **Standard Services**: 30-60 seconds
- **Non-Critical Services**: 60-120 seconds

### 3. Service Criticality

Mark services as critical based on impact:
- `critical: true` - Will trigger rollback
- `critical: false` - Will log warnings only

### 4. Testing

Always test in dry-run mode first:
```bash
python scripts/rollback_automation.py --dry-run --verbose
```

### 5. Log Rotation

Configure log rotation to prevent disk space issues:
```bash
# /etc/logrotate.d/rollback-automation
/var/log/rollback_automation.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

## Troubleshooting

### Script Won't Start

**Issue**: Permission denied or module not found

**Solution**:
```bash
# Make script executable
chmod +x scripts/rollback_automation.py

# Install dependencies
pip install -r requirements.txt asyncpg httpx
```

### Docker Commands Fail

**Issue**: Cannot connect to Docker daemon

**Solution**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Or run with sudo (not recommended)
sudo python scripts/rollback_automation.py
```

### False Positives

**Issue**: Services being rolled back unnecessarily

**Solution**:
- Increase failure threshold
- Increase check interval
- Increase timeout
- Review health endpoint implementation

### Rollback Fails

**Issue**: Rollback initiated but service doesn't start

**Solution**:
1. Check Docker image availability
2. Review docker-compose.yml configuration
3. Check logs: `docker compose logs service_name`
4. Manually verify previous image exists

### No Previous Image Found

**Issue**: Cannot rollback - no previous version

**Solution**:
- Ensure Docker images are tagged with versions
- Use image retention policy
- Tag images before deployment:
  ```bash
  docker tag service:latest service:v1.0.0
  docker tag service:latest service:backup_$(date +%Y%m%d)
  ```

## Advanced Usage

### Custom Health Check Logic

Extend the `HealthMonitor` class for custom checks:

```python
async def check_custom_metric(self, endpoint: ServiceEndpoint) -> HealthCheckResult:
    # Your custom health check logic
    pass
```

### Post-Rollback Actions

Add hooks after rollback:

```python
def post_rollback_hook(self, service_name: str):
    # Send notifications
    # Update monitoring dashboards
    # Trigger alerts
    pass
```

### Integration with Monitoring Tools

Export metrics to Prometheus:
```python
from prometheus_client import Counter, Gauge

rollback_counter = Counter('rollbacks_total', 'Total rollbacks')
health_status = Gauge('service_health', 'Service health status', ['service'])
```

## Security Considerations

1. **Credentials**: Store database passwords in environment variables
2. **Docker Socket**: Limit access to Docker socket
3. **Log Files**: Restrict log file permissions (chmod 600)
4. **Service Account**: Run with minimal required permissions
5. **Network**: Restrict network access to health endpoints

## Performance

- **CPU Usage**: Minimal (< 1% on average)
- **Memory**: ~50-100 MB
- **Network**: Depends on number of endpoints and check frequency
- **Disk I/O**: Minimal (logging only)

## Support

For issues or questions:
1. Check logs: `rollback_automation_YYYYMMDD.log`
2. Review rollback history: `rollback_history_*.json`
3. Run with `--verbose` flag for detailed output
4. Test with `--dry-run` to debug without changes

## License

Part of the GSC Site Data Warehouse project.
