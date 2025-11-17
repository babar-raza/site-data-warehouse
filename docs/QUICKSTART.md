# Quick Start Guide
## Deploy Hybrid Insight Engine in 15 Minutes

---

## Prerequisites Checklist

- [ ] **PostgreSQL 13+** installed
- [ ] **Python 3.9+** installed  
- [ ] **Docker & Docker Compose** installed
- [ ] **Google Cloud Service Account** with GSC API access
- [ ] **(Optional)** GA4 API credentials

---

## Step 1: Clone Repository (1 min)

```bash
git clone <repository-url>
cd gsc-data-warehouse
```

---

## Step 2: Setup Environment (3 min)

### Create `.env` file
```bash
cat > .env << 'ENV_EOF'
# Database
WAREHOUSE_DSN=postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db

# GSC API
GSC_SA_PATH=/path/to/gsc_sa.json
GSC_PROPERTY=sc-domain:example.com

# GA4 (Optional)
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_PATH=/path/to/ga4_credentials.json
ENV_EOF
```

### Setup GSC credentials
```bash
cp secrets/gsc_sa.json.template secrets/gsc_sa.json
# Edit secrets/gsc_sa.json with your service account credentials
```

---

## Step 3: Start Database (2 min)

```bash
docker-compose up -d warehouse

# Wait for health check
until docker-compose exec warehouse pg_isready; do sleep 1; done
```

---

## Step 4: Run Migrations (2 min)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run all SQL migrations
for script in sql/*.sql; do
    psql $WAREHOUSE_DSN -f "$script"
done

# Verify setup
psql $WAREHOUSE_DSN -c "SELECT * FROM gsc.validate_unified_view_time_series();"
```

**Expected output:** All checks should show `PASS` or `INFO`

---

## Step 5: Ingest Data (5 min)

```bash
# Ingest last 30 days of GSC data
python ingestors/api/gsc_api_ingestor.py \
    --date-start $(date -d '30 days ago' +%Y-%m-%d) \
    --date-end $(date +%Y-%m-%d)

# Verify data loaded
psql $WAREHOUSE_DSN -c "
    SELECT 
        COUNT(*) as rows,
        MIN(date) as earliest,
        MAX(date) as latest
    FROM gsc.fact_gsc_daily;"
```

**Expected:** 1000+ rows spanning 30 days

---

## Step 6: Generate Insights (2 min)

```bash
# Run Insight Engine
python -m insights_core.cli refresh

# View insights
psql $WAREHOUSE_DSN -c "
    SELECT 
        category,
        severity,
        title,
        description
    FROM gsc.vw_insights_actionable
    LIMIT 10;"
```

**Expected:** Insights showing risks, opportunities, or trends

---

## ✅ Success! What's Next?

### Option A: Start All Services
```bash
docker-compose up -d
docker-compose ps  # Verify all services running
```

### Option B: Schedule Automated Collection
```bash
# Add to crontab
0 2 * * * cd /path/to/project && python -m insights_core.cli refresh
```

### Option C: Connect Claude Desktop (MCP)
```bash
# Start MCP server
docker-compose up -d mcp

# Configure Claude Desktop
# Add to claude_desktop_config.json:
{
  "mcpServers": {
    "gsc-warehouse": {
      "command": "docker",
      "args": ["exec", "gsc_mcp", "python", "/app/mcp/mcp_server.py"]
    }
  }
}
```

---

## Troubleshooting

### Issue: `psql: connection refused`
**Fix:** Ensure PostgreSQL is running
```bash
docker-compose up -d warehouse
docker-compose logs warehouse
```

### Issue: `ERROR: relation does not exist`
**Fix:** Run migrations
```bash
for script in sql/*.sql; do psql $WAREHOUSE_DSN -f "$script"; done
```

### Issue: `No insights generated`
**Reason:** May be no anomalies (expected if traffic is stable)
**Check:**
```sql
SELECT COUNT(*) FROM gsc.vw_unified_anomalies;
```

---

## Next Steps

- **Read full README:** [`README.md`](README.md)
- **Understand architecture:** [`ARCHITECTURE.md`](ARCHITECTURE.md)
- **Write custom detectors:** [`guides/DETECTOR_GUIDE.md`](guides/DETECTOR_GUIDE.md)
- **Production deployment:** [`deployment/PRODUCTION_GUIDE.md`](deployment/PRODUCTION_GUIDE.md)

**Questions?** See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
