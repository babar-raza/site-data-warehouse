# Troubleshooting Guide
## Common Issues and Solutions

---

## Database Issues

### Issue: Connection Refused

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Diagnosis:**
```bash
# Check if PostgreSQL is running
docker-compose ps warehouse

# Check container logs
docker-compose logs warehouse
```

**Solutions:**
1. Start database: `docker-compose up -d warehouse`
2. Wait for health check: `until docker-compose exec warehouse pg_isready; do sleep 1; done`
3. Verify connection: `psql $WAREHOUSE_DSN -c "SELECT 1;"`

---

### Issue: Table/View Does Not Exist

**Symptoms:**
```
ERROR: relation "gsc.vw_unified_page_performance" does not exist
```

**Diagnosis:**
```sql
-- List all views
SELECT schemaname, viewname 
FROM pg_views 
WHERE schemaname = 'gsc';
```

**Solution:** Run migrations
```bash
for script in sql/*.sql; do
    psql $WAREHOUSE_DSN -f "$script"
done
```

---

### Issue: WoW/MoM Calculations Are NULL

**Symptoms:**
```sql
SELECT gsc_clicks_change_wow FROM gsc.vw_unified_page_performance;
-- All values are NULL
```

**Diagnosis:**
```sql
-- Check data depth
SELECT 
    COUNT(DISTINCT date) as days,
    MIN(date) as earliest,
    MAX(date) as latest
FROM gsc.fact_gsc_daily;
```

**Root Cause:** Need 7+ days for WoW, 28+ days for MoM

**Solution:** Backfill historical data
```bash
python scripts/backfill_historical.py --days 30
```

---

## Data Ingestion Issues

### Issue: No Data Ingested

**Symptoms:**
```sql
SELECT COUNT(*) FROM gsc.fact_gsc_daily;
-- Returns 0
```

**Diagnosis:**
```bash
# Run ingestor with verbose logging
python ingestors/api/gsc_api_ingestor.py \
    --date-start 2024-11-01 \
    --date-end 2024-11-15 \
    --log-level DEBUG
```

**Common Causes:**
1. **Invalid GSC credentials**
   - Check `secrets/gsc_sa.json` format
   - Verify service account has GSC API access
   
2. **Invalid property**
   - Verify property name: `sc-domain:example.com`
   - Check GSC account has access to property

3. **API quota exceeded**
   - Wait 24 hours
   - Check quota in Google Cloud Console

**Solutions:**
```bash
# Test GSC API connection
python -c "
from google.oauth2 import service_account
from googleapiclient.discovery import build

credentials = service_account.Credentials.from_service_account_file(
    'secrets/gsc_sa.json',
    scopes=['https://www.googleapis.com/auth/webmasters.readonly']
)
service = build('searchconsole', 'v1', credentials=credentials)
sites = service.sites().list().execute()
print(sites)
"
```

---

### Issue: Partial Data Loaded

**Symptoms:**
```sql
SELECT date, COUNT(*) 
FROM gsc.fact_gsc_daily 
GROUP BY date 
ORDER BY date;
-- Some dates missing
```

**Diagnosis:**
```sql
-- Check for gaps
SELECT 
    date,
    date - LAG(date) OVER (ORDER BY date) as gap
FROM (
    SELECT DISTINCT date 
    FROM gsc.fact_gsc_daily
) t
WHERE (date - LAG(date) OVER (ORDER BY date)) > 1;
```

**Solution:** Re-ingest missing dates
```bash
python ingestors/api/gsc_api_ingestor.py \
    --date-start 2024-11-05 \
    --date-end 2024-11-05 \
    --force
```

---

## Insight Engine Issues

### Issue: No Insights Generated

**Symptoms:**
```sql
SELECT COUNT(*) FROM gsc.insights;
-- Returns 0
```

**Diagnosis:**
```sql
-- Check if anomalies exist
SELECT COUNT(*) FROM gsc.vw_unified_anomalies;

-- Check detector thresholds
SELECT 
    property,
    page_path,
    gsc_clicks_change_wow,
    ga_conversions_change_wow
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY gsc_clicks_change_wow;
```

**Root Cause Options:**
1. **No anomalies** (traffic is stable - expected!)
2. **Thresholds too strict**
3. **Not enough data**

**Solutions:**

**If no anomalies:** This is expected! System works correctly.

**If thresholds too strict:** Adjust in `insights_core/config.py`
```python
class InsightsConfig:
    risk_threshold_clicks_pct: float = -15  # Changed from -20
    opportunity_threshold_impressions_pct: float = 30  # Changed from 50
```

**If not enough data:** Backfill more history
```bash
python scripts/backfill_historical.py --days 90
```

---

### Issue: Detector Fails with Exception

**Symptoms:**
```
ERROR insights_core.engine - AnomalyDetector failed: division by zero
```

**Diagnosis:**
```bash
# Run detector in debug mode
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)

from insights_core.detectors import AnomalyDetector
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig
import os

repo = InsightRepository(os.environ['WAREHOUSE_DSN'])
config = InsightsConfig()
detector = AnomalyDetector(repo, config)

try:
    count = detector.detect()
    print(f'Success: {count} insights')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
"
```

**Common Causes:**
1. Division by zero (clicks_7d_ago = 0)
2. NULL values in calculations
3. Data type mismatches

**Solution:** Check detector implementation for NULL handling
```python
# ✅ CORRECT
if row['gsc_clicks_7d_ago'] and row['gsc_clicks_7d_ago'] > 0:
    change = ((clicks - clicks_7d_ago) / clicks_7d_ago) * 100
else:
    change = None

# ❌ WRONG (can divide by zero)
change = ((clicks - clicks_7d_ago) / clicks_7d_ago) * 100
```

---

## Performance Issues

### Issue: Slow Queries on Unified View

**Symptoms:**
```sql
EXPLAIN ANALYZE
SELECT * FROM gsc.vw_unified_page_performance
WHERE date >= '2024-01-01';
-- Execution time: 30 seconds
```

**Diagnosis:**
```sql
-- Check if indexes exist
SELECT 
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'gsc'
    AND tablename IN ('fact_gsc_daily', 'fact_ga4_daily');
```

**Solution 1:** Create indexes
```sql
CREATE INDEX IF NOT EXISTS idx_fact_gsc_date_property_url 
    ON gsc.fact_gsc_daily(date DESC, property, url);

CREATE INDEX IF NOT EXISTS idx_fact_ga4_date_property_page 
    ON gsc.fact_ga4_daily(date DESC, property, page_path);
```

**Solution 2:** Use materialized view for large datasets
```sql
CREATE MATERIALIZED VIEW gsc.mv_unified_page_performance AS
SELECT * FROM gsc.vw_unified_page_performance;

-- Refresh daily
REFRESH MATERIALIZED VIEW CONCURRENTLY gsc.mv_unified_page_performance;
```

---

### Issue: Insight Engine Times Out

**Symptoms:**
```
TimeoutError: Insight detection exceeded 5 minutes
```

**Diagnosis:**
```bash
# Time each detector
time python -c "
from insights_core.detectors import AnomalyDetector
# ... run detector
"
```

**Solution:** Optimize detector query
```python
# ✅ GOOD: Filter early, use indexes
query = """
    SELECT DISTINCT ON (property, page_path)
        *
    FROM gsc.vw_unified_page_performance
    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
        AND property = %s
    ORDER BY property, page_path, date DESC
"""

# ❌ BAD: Loads everything, filters in Python
query = "SELECT * FROM gsc.vw_unified_page_performance"
filtered = [r for r in rows if r['property'] == target_property]
```

---

## Docker Issues

### Issue: Services Won't Start

**Symptoms:**
```bash
docker-compose up -d
# Services exit immediately
```

**Diagnosis:**
```bash
# Check service logs
docker-compose logs --tail=50 insights_engine

# Check container status
docker-compose ps
```

**Common Causes:**
1. Port already in use
2. Missing secrets
3. Database not ready

**Solutions:**

**Port conflict:**
```bash
# Find process using port
lsof -i :5432
# Kill or change port in docker-compose.yml
```

**Missing secrets:**
```bash
# Check secrets exist
ls -la secrets/
# Create missing secrets
cp secrets/gsc_sa.json.template secrets/gsc_sa.json
```

**Database not ready:**
```bash
# Wait for database
until docker-compose exec warehouse pg_isready; do
    echo "Waiting for database..."
    sleep 2
done
```

---

## Multi-Agent System Issues

### Issue: Agents Not Running

**Symptoms:**
```sql
SELECT * FROM gsc.agent_executions ORDER BY started_at DESC LIMIT 5;
-- No recent executions
```

**Diagnosis:**
```bash
# Check dispatcher logs
docker-compose logs dispatcher

# Manually run agents
python agents/dispatcher/dispatcher_agent.py --mode full
```

**Common Causes:**
1. Dispatcher not scheduled
2. Database permissions
3. Message bus configuration

**Solutions:**

**Add to scheduler:**
```bash
# Edit crontab
0 3 * * * cd /path/to/project && python agents/dispatcher/dispatcher_agent.py
```

**Check permissions:**
```sql
GRANT ALL ON SCHEMA gsc TO gsc_user;
GRANT ALL ON ALL TABLES IN SCHEMA gsc TO gsc_user;
```

---

## MCP Server Issues

### Issue: Claude Can't Connect

**Symptoms:**
```
Claude says: "I don't have access to your GSC data"
```

**Diagnosis:**
```bash
# Check MCP server is running
docker-compose ps mcp

# Test MCP endpoint
curl http://localhost:8000/health
```

**Solution:**
```bash
# Start MCP server
docker-compose up -d mcp

# Configure Claude Desktop
# Edit ~/.claude/claude_desktop_config.json
{
  "mcpServers": {
    "gsc-warehouse": {
      "command": "docker",
      "args": ["exec", "-i", "gsc_mcp", "python", "/app/mcp/mcp_server.py"]
    }
  }
}
```

---

## Getting More Help

### Enable Debug Logging

```python
# Add to script
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check System Health

```bash
# Run validation script
python scripts/validate_data.py

# Check database health
psql $WAREHOUSE_DSN -c "
    SELECT * FROM gsc.validate_unified_view_time_series();
    SELECT * FROM gsc.validate_insights_table();
"
```

### Review Logs

```bash
# Docker logs
docker-compose logs --tail=100

# Application logs
tail -f logs/insights_engine.log
tail -f logs/agents.log
```

---

**Still stuck?** Check:
- [Architecture documentation](ARCHITECTURE.md)
- [Unified view guide](guides/UNIFIED_VIEW_GUIDE.md)
- [E2E test plan](E2E_TEST_PLAN.md)
