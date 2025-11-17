# Windows Quick Start Guide

## Prerequisites Installation

### 1. Install Docker Desktop
1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop
2. Run the installer
3. Start Docker Desktop
4. Ensure WSL 2 is enabled (Docker Desktop will prompt if needed)
5. Verify installation:
   ```batch
   docker --version
   docker compose version
   ```

### 2. Configure Docker Desktop
1. Open Docker Desktop
2. Go to Settings → Resources
3. Set Memory to at least 4GB (recommended: 8GB)
4. Set Disk image size to at least 30GB
5. Click "Apply & Restart"

## Setup Process

### Step 1: Get Google Cloud Credentials

1. Go to Google Cloud Console: https://console.cloud.google.com
2. Create or select a project
3. Enable APIs:
   - BigQuery API
   - Google Search Console API
4. Create Service Account:
   - Go to IAM & Admin → Service Accounts
   - Click "Create Service Account"
   - Give it a name (e.g., "gsc-warehouse")
   - Grant roles:
     * BigQuery Data Viewer
     * BigQuery Job User
   - Create key (JSON format)
   - Download the JSON file

5. Add service account to Search Console:
   - Go to https://search.google.com/search-console
   - Select your property
   - Settings → Users and permissions
   - Add the service account email as a user

### Step 2: Configure Project

1. Place your downloaded JSON file as `secrets\gsc_sa.json`

2. Edit `.env` file with your details:
   ```
   GCP_PROJECT_ID=your-actual-project-id
   BQ_DATASET=searchconsole
   ```
   (Replace `your-actual-project-id` with your real GCP project ID)

### Step 3: Validate Setup

Before deploying, validate your setup:
```batch
validate-setup.bat
```

This will check:
- Docker installation
- Required files
- Credentials
- Directory structure

### Step 4: Deploy

#### Option A: Full Automated Deployment
Deploy everything and start collecting data immediately:
```batch
start-collection.bat
```

This will:
1. Build all Docker images
2. Start the database
3. Run initial data ingestion
4. Start all services
5. Enable automated scheduling

**Total time: 10-15 minutes**

#### Option B: Step-by-Step Deployment
For more control, deploy in stages:

1. Deploy infrastructure only:
   ```batch
   deploy.bat
   ```

2. Manually trigger data collection:
   ```batch
   REM Extract from BigQuery
   docker compose --profile ingestion run --rm bq_extractor python bq_extractor.py
   
   REM Ingest from API
   docker compose --profile ingestion run --rm api_ingestor python gsc_api_ingestor.py
   
   REM Apply transforms
   docker compose --profile transform run --rm transformer python apply_transforms.py
   ```

3. Start scheduler for automation:
   ```batch
   docker compose --profile scheduler up -d scheduler
   ```

### Step 5: Verify Deployment

Check service health:
```batch
health-check.bat
```

View running containers:
```batch
docker compose ps
```

Check logs:
```batch
docker compose logs -f
```

## Access Points

After deployment, access services at:

| Service | URL | Purpose |
|---------|-----|---------|
| Database | `localhost:5432` | PostgreSQL warehouse |
| MCP Server | `http://localhost:8000` | AI agent integration |
| MCP Health | `http://localhost:8000/health` | Health check |
| Insights API | `http://localhost:8001` | REST API |
| Metrics | `http://localhost:9090` | Prometheus metrics |
| Prometheus UI | `http://localhost:9091` | Metrics dashboard |

### Test the API

```batch
REM Health check
curl http://localhost:8000/health

REM Get page health data
curl http://localhost:8001/api/page-health

REM Get query trends
curl http://localhost:8001/api/query-trends
```

## Data Collection Schedule

The scheduler automatically runs:
- **Daily at 02:00 UTC**: API ingestion
- **Weekly (Sunday) at 03:00 UTC**: Full reconciliation

To change schedules, edit `scheduler/scheduler.py`

## Common Commands

### View Logs
```batch
REM All services
docker compose logs

REM Specific service
docker compose logs -f mcp

REM Last 100 lines
docker compose logs --tail=100
```

### Stop Services
```batch
REM Stop all
docker compose down

REM Stop specific service
docker compose stop mcp
```

### Restart Services
```batch
REM Restart all
docker compose restart

REM Restart specific
docker compose restart warehouse
```

### Manual Data Collection
```batch
REM One-time data collection
docker compose --profile ingestion up bq_extractor api_ingestor
```

### Complete Cleanup
⚠️ **WARNING: This deletes all data**
```batch
cleanup.bat
```

## Troubleshooting

### "Docker is not running"
**Solution**: 
- Open Docker Desktop
- Wait for the whale icon to become steady (not animated)
- Try command again

### "secrets/gsc_sa.json not found"
**Solution**:
- Ensure you've downloaded the service account JSON from Google Cloud
- Place it exactly at: `secrets\gsc_sa.json`
- Verify it's valid JSON (open in notepad)

### "Port already in use"
**Solution**:
- Check what's using the port: `netstat -ano | findstr :5432`
- Stop the conflicting service
- Or change the port in `docker-compose.yml`

### "Failed to connect to BigQuery"
**Solution**:
1. Verify service account has correct permissions
2. Check project ID in `.env` matches your GCP project
3. Verify BigQuery API is enabled in GCP Console

### "Out of disk space"
**Solution**:
- Clean Docker: `docker system prune -a`
- Increase Docker disk allocation in Docker Desktop settings

### Container won't start
**Solution**:
```batch
REM Check logs
docker compose logs [service-name]

REM Rebuild
docker compose build --no-cache [service-name]
docker compose up -d [service-name]
```

## Next Steps

1. **Connect to Database**
   - Use any PostgreSQL client
   - Host: `localhost`
   - Port: `5432`
   - Database: `gsc_db`
   - User: `gsc_user`
   - Password: (from `secrets\db_password.txt`)

2. **Query the Data**
   ```sql
   -- See available views
   \dt gsc.*
   
   -- Page health
   SELECT * FROM gsc.vw_page_health_28d LIMIT 10;
   
   -- Query trends
   SELECT * FROM gsc.vw_query_winners_losers_28d_vs_prev LIMIT 10;
   ```

3. **Set Up Monitoring**
   ```batch
   REM Start Prometheus and metrics
   docker compose --profile observability up -d
   
   REM Access Prometheus UI
   start http://localhost:9091
   ```

4. **Enable Insights API**
   ```batch
   docker compose --profile api up -d insights_api
   ```

## Support Resources

- **Full Documentation**: See `README.md`
- **Deployment Guide**: See `DEPLOYMENT.md`
- **Health Check**: Run `health-check.bat`
- **Validate Setup**: Run `validate-setup.bat`

## File Structure

```
gsc-warehouse-pipeline/
├── deploy.bat              ← Deploy infrastructure
├── start-collection.bat    ← Deploy + start data collection
├── cleanup.bat             ← Remove everything
├── health-check.bat        ← Check system health
├── validate-setup.bat      ← Pre-deployment validation
├── .env                    ← Your configuration
├── secrets/
│   ├── gsc_sa.json        ← Your GCP credentials (you provide)
│   └── db_password.txt     ← Database password
└── logs/                   ← Application logs
```

## Security Notes

1. **Never commit `secrets/gsc_sa.json`** - It's in `.gitignore`
2. **Rotate service account keys** regularly (every 90 days)
3. **Use strong database passwords** in production
4. **Don't expose ports** to the internet without authentication

---

**Ready to deploy?** Run:
```batch
validate-setup.bat
start-collection.bat
```

**Questions?** Check `DEPLOYMENT.md` for detailed troubleshooting.
