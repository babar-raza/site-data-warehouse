# Screenshot Capture Guide

## Quick Start

To capture screenshots of all UI components in the SEO Intelligence Platform:

### 1. Start Docker Desktop
First, ensure Docker Desktop is running on your Windows machine.

### 2. Start the Platform Services

```bash
# Start all required services (database, APIs, monitoring)
docker-compose --profile core --profile insights --profile api up -d

# Wait for services to be healthy (30-60 seconds)
docker-compose ps
```

### 3. Run the Screenshot Script

```bash
# Basic usage - captures all 31 endpoints
python scripts/take_screenshots.py

# Custom output directory
python scripts/take_screenshots.py --output my_screenshots/

# Run with visible browser (see what's happening)
python scripts/take_screenshots.py --no-headless
```

## What Gets Captured

The script automatically captures **31 endpoints** across multiple categories:

### Grafana Dashboards (11 dashboards)
Auto-discovered from JSON files:
- ✅ Actions Command Center
- ✅ Alert Status
- ✅ Application Metrics
- ✅ Core Web Vitals Monitoring
- ✅ Database Performance
- ✅ GA4 Analytics Overview
- ✅ GSC Data Overview
- ✅ Hybrid Analytics (GSC + GA4 Unified)
- ✅ Infrastructure Overview
- ✅ SERP Position Tracking
- ✅ Service Health

### Grafana UI Pages (4 pages)
- Home page
- Dashboards list
- Explore interface
- Alerting interface

### Prometheus (5 pages)
- Home
- Targets
- Alerts
- Configuration
- Graph interface

### Container Monitoring (2 pages)
- cAdvisor containers view
- cAdvisor Docker overview

### API Documentation (6 endpoints)
- Insights API Swagger docs
- Insights API ReDoc
- Insights API health
- MCP Server Swagger docs
- MCP Server ReDoc
- MCP Server health

### Metrics Exporters (3 endpoints)
- Custom application metrics
- PostgreSQL database metrics
- Redis cache metrics

## Output

Screenshots are saved to `screenshots/` with the format:
```
YYYYMMDD_HHMMSS_endpoint_name.png
```

Example:
```
20251128_112735_01_grafana_home.png
20251128_112735_dashboard_gsc_overview.png
20251128_112735_30_insights_api_docs.png
```

## Features

- ✅ **Auto-discovery**: Automatically finds all Grafana dashboards from JSON files
- ✅ **Authentication**: Handles Grafana login automatically
- ✅ **Full-page screenshots**: Captures entire page, not just viewport
- ✅ **Error handling**: Gracefully handles unavailable services
- ✅ **Progress reporting**: Shows detailed progress and summary
- ✅ **Categorized output**: Organized by service type

## Troubleshooting

### Docker not running
```
Error: unable to get image... The system cannot find the file specified
```
**Solution**: Start Docker Desktop first

### Services not responding
```
Error: net::ERR_CONNECTION_REFUSED at http://localhost:3000/
```
**Solution**: Wait for services to start (check with `docker-compose ps`)

### Playwright not installed
```
Error: No module named 'playwright'
```
**Solution**:
```bash
pip install playwright
python -m playwright install chromium
```

## Advanced Usage

### Capture Only Specific Services

Modify the script to comment out endpoints you don't need in the `base_endpoints` dictionary.

### Adjust Viewport Size

Edit line 369 in the script:
```python
viewport={"width": 1920, "height": 1080}  # Change these values
```

### Custom Wait Times

For slower systems, increase wait times on lines:
- Line 326: `await page.wait_for_timeout(3000)` - General wait
- Line 329: `await page.wait_for_timeout(5000)` - Dashboard render wait

## Requirements

- Python 3.11+
- Playwright: `pip install playwright`
- Chromium browser: `python -m playwright install chromium`
- Docker Desktop running
- Services started with docker-compose

## Script Location

The screenshot script is located at:
```
scripts/take_screenshots.py
```
