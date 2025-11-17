# Troubleshooting Guide

## Quick Reference

| Issue | First Check | Quick Fix |
|-------|-------------|-----------|
| Data not ingesting | API credentials | Run `validate-setup.sh` |
| Agent not starting | Database connection | Check `.env` configuration |
| High CPU usage | Agent count | Scale down concurrent agents |
| Disk space full | Log files | Run `cleanup.sh` |
| Slow queries | Missing indexes | Run `ANALYZE` on tables |

## Common Issues

### 1. Data Ingestion Problems

#### Issue: GSC API Returns No Data

**Symptoms:**
- Ingestion completes but no rows inserted
- "No data available" in logs

**Diagnosis:**
```bash
# Check API credentials
python -c "from ingestors.api.gsc_api_ingestor import GSCAPIIngestor; \
    ingestor = GSCAPIIngestor('sc-domain:yourdomain.com', 'credentials.json', {}); \
    print(ingestor.test_connection())"

# Verify property access
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://searchconsole.googleapis.com/v1/webmasters/sites"
```

**Solutions:**
1. Verify property URL format (must include `sc-domain:` prefix)
2. Check date range (GSC data has 2-3 day delay)
3. Confirm service account has property access in GSC console
4. Review API quota limits

**Prevention:**
- Set up API quota monitoring
- Implement data freshness alerts

---

#### Issue: GA4 Data Not Syncing

**Symptoms:**
- GA4 tables empty or stale
- "Authentication failed" errors

**Diagnosis:**
```bash
# Test GA4 connection
python -c "from ingestors.ga4.ga4_extractor import GA4Extractor; \
    extractor = GA4Extractor('123456789', 'ga4-credentials.json', {}); \
    print(extractor.test_connection())"

# Check property ID
echo $GA4_PROPERTY_ID
```

**Solutions:**
1. Verify GA4 property ID (numeric only, no 'G-' prefix)
2. Check service account permissions in GA4
3. Ensure Analytics Data API is enabled
4. Review API quota usage

**Prevention:**
- Document correct property ID format
- Set up credential expiration alerts

---

#### Issue: Rate Limit Exceeded

**Symptoms:**
- HTTP 429 errors in logs
- Intermittent data gaps
- "Rate limit exceeded" messages

**Diagnosis:**
```bash
# Check current rate limit status
grep "rate limit" logs/app.log | tail -20

# View API quota usage
gcloud logging read "resource.type=api" --limit 100
```

**Solutions:**
1. Reduce ingestion frequency
2. Implement exponential backoff
3. Spread API calls across time
4. Request quota increase from Google

**Prevention:**
```python
# Configure rate limiter in .env
RATE_LIMIT_CALLS_PER_MINUTE=100
RATE_LIMIT_CALLS_PER_DAY=10000
```

---

### 2. Agent Issues

#### Issue: Agents Not Starting

**Symptoms:**
- Agent initialization fails
- "Connection refused" errors
- Agents in ERROR status

**Diagnosis:**
```bash
# Check agent status
python -c "from agents.watcher.watcher_agent import WatcherAgent; \
    import asyncio; \
    agent = WatcherAgent('test', {'host': 'localhost', 'port': 5432, 'user': 'gsc_user', 'password': 'pass', 'database': 'gsc_warehouse'}); \
    print(asyncio.run(agent.initialize()))"

# Verify database connectivity
psql -U gsc_user -d gsc_warehouse -c "SELECT 1"

# Check agent logs
tail -f logs/agents/watcher_*.log
```

**Solutions:**
1. Verify database credentials in `.env`
2. Check database is running: `systemctl status postgresql`
3. Ensure database user has correct permissions
4. Review firewall rules if remote database

**Prevention:**
- Implement health check monitoring
- Set up automatic agent restart on failure

---

#### Issue: Agent Performance Degradation

**Symptoms:**
- Processing time increases over time
- High memory usage
- Slow response times

**Diagnosis:**
```bash
# Check agent resource usage
ps aux | grep python | grep agent

# Monitor memory usage
watch -n 1 'ps -o pid,comm,vsz,rss,pmem --sort=-rss | head -20'

# Check for memory leaks
python -m memory_profiler agents/watcher/watcher_agent.py
```

**Solutions:**
1. Restart agents: `./stop.sh && ./bootstrap.py`
2. Reduce concurrent agent count
3. Increase agent resource limits
4. Check for memory leaks in custom code
5. Review database connection pooling

**Prevention:**
```python
# Configure agent limits
AGENT_MAX_MEMORY_MB=2048
AGENT_PROCESSING_TIMEOUT=300
AGENT_RESTART_INTERVAL=3600
```

---

#### Issue: Message Bus Congestion

**Symptoms:**
- Messages not delivered
- High dead letter queue count
- Agent communication delays

**Diagnosis:**
```bash
# Check message bus stats
python -c "from agents.base.message_bus import MessageBus; \
    import asyncio; \
    bus = MessageBus(); \
    asyncio.run(bus.start()); \
    print(bus.get_stats())"

# View dead letter queue
ls -lh data/messages/dead_letters/
```

**Solutions:**
1. Restart message bus
2. Clear dead letter queue: `rm -rf data/messages/dead_letters/*`
3. Increase message TTL
4. Add more worker threads
5. Review subscriber handlers for blocking code

**Prevention:**
- Monitor message bus queue depth
- Set up dead letter alerts
- Implement message archiving

---

### 3. Database Issues

#### Issue: Slow Query Performance

**Symptoms:**
- Queries taking > 5 seconds
- High database CPU usage
- Application timeouts

**Diagnosis:**
```sql
-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE mean_exec_time > 1000
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check missing indexes
SELECT schemaname, tablename, attname
FROM pg_stats
WHERE n_distinct > 100
AND schemaname IN ('gsc', 'ga4')
AND NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = pg_stats.schemaname
    AND tablename = pg_stats.tablename
    AND indexdef LIKE '%' || attname || '%'
);

-- Analyze table statistics
ANALYZE gsc.search_analytics;
ANALYZE ga4.page_metrics;
```

**Solutions:**
1. Add missing indexes
2. Update table statistics: `ANALYZE`
3. Vacuum tables: `VACUUM ANALYZE`
4. Optimize query plans
5. Consider table partitioning

**Prevention:**
```sql
-- Schedule regular maintenance
CREATE EXTENSION IF NOT EXISTS pg_cron;
SELECT cron.schedule('vacuum-gsc', '0 2 * * *', 'VACUUM ANALYZE gsc.search_analytics');
```

---

#### Issue: Materialized View Refresh Fails

**Symptoms:**
- View refresh errors in logs
- Stale data in views
- "CONCURRENTLY cannot be used" errors

**Diagnosis:**
```bash
# Check view refresh status
python warehouse/refresh_views.py --stats

# View errors
psql -U gsc_user -d gsc_warehouse -c "
SELECT * FROM pg_stat_progress_create_index
WHERE command = 'CREATE INDEX CONCURRENTLY';
"
```

**Solutions:**
1. Use non-concurrent refresh: `--no-concurrent`
2. Check for unique indexes on views
3. Verify sufficient disk space
4. Kill blocking queries
5. Drop and recreate view if corrupted

**Prevention:**
```bash
# Schedule view refresh with monitoring
*/30 * * * * /path/to/refresh_views.py --view all || mail -s "View Refresh Failed" ops@example.com
```

---

#### Issue: Connection Pool Exhausted

**Symptoms:**
- "connection pool exhausted" errors
- Application hangs
- "FATAL: too many connections" errors

**Diagnosis:**
```sql
-- Check active connections
SELECT count(*), state
FROM pg_stat_activity
WHERE datname = 'gsc_warehouse'
GROUP BY state;

-- Identify long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;
```

**Solutions:**
1. Increase pool size temporarily
2. Kill idle connections: `SELECT pg_terminate_backend(pid)`
3. Restart connection pools
4. Review application connection handling
5. Increase `max_connections` in postgresql.conf

**Prevention:**
```python
# Configure appropriate pool sizes
asyncpg.create_pool(
    min_size=10,
    max_size=50,
    max_inactive_connection_lifetime=300
)
```

---

### 4. Performance Issues

#### Issue: High CPU Usage

**Symptoms:**
- System load > 4.0
- Slow response times
- High context switching

**Diagnosis:**
```bash
# Check CPU usage by process
top -b -n 1 | head -20

# Identify CPU-intensive queries
psql -U gsc_user -d gsc_warehouse -c "
SELECT pid, query, state, 
       now() - query_start as runtime
FROM pg_stat_activity 
WHERE state = 'active'
ORDER BY runtime DESC;
"

# Check agent CPU usage
ps -eo pid,comm,pcpu --sort=-pcpu | grep python | head -10
```

**Solutions:**
1. Scale down concurrent agents
2. Optimize database queries
3. Add query caching
4. Increase server resources
5. Implement query timeout limits

**Prevention:**
- Monitor CPU usage trends
- Set up CPU threshold alerts (> 80%)
- Implement auto-scaling

---

#### Issue: Memory Issues

**Symptoms:**
- Out of memory errors
- System swapping heavily
- Process killed by OOM killer

**Diagnosis:**
```bash
# Check memory usage
free -h

# Check swap usage
swapon --show

# Find memory-hungry processes
ps aux --sort=-%mem | head -20

# Check OOM killer logs
dmesg | grep -i "out of memory"
```

**Solutions:**
1. Restart memory-intensive agents
2. Reduce batch sizes in ingestion
3. Clear caches
4. Add more RAM
5. Enable swap if needed

**Prevention:**
```python
# Configure memory limits
AGENT_MAX_MEMORY_MB=2048
INGESTOR_BATCH_SIZE=1000  # Reduce if memory constrained
```

---

### 5. Data Quality Issues

#### Issue: Data Gaps

**Symptoms:**
- Missing dates in data
- Incomplete records
- Gaps in time series

**Diagnosis:**
```sql
-- Check for date gaps
SELECT date, count(*) 
FROM gsc.search_analytics 
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date 
ORDER BY date;

-- Find missing data ranges
SELECT 
    d.date,
    COALESCE(sa.records, 0) as records
FROM generate_series(
    CURRENT_DATE - INTERVAL '30 days',
    CURRENT_DATE,
    INTERVAL '1 day'
) AS d(date)
LEFT JOIN (
    SELECT date, count(*) as records
    FROM gsc.search_analytics
    GROUP BY date
) sa ON d.date = sa.date
WHERE COALESCE(sa.records, 0) = 0;
```

**Solutions:**
1. Run backfill for missing dates
2. Check ingestion logs for errors
3. Verify API access during gap period
4. Re-run failed ingestion jobs

**Prevention:**
- Monitor data freshness daily
- Set up gap detection alerts
- Implement automatic backfill

---

#### Issue: Duplicate Data

**Symptoms:**
- Inflated metrics
- Duplicate rows in tables
- Constraint violations

**Diagnosis:**
```sql
-- Find duplicates
SELECT property, date, page, query, COUNT(*)
FROM gsc.search_analytics
GROUP BY property, date, page, query
HAVING COUNT(*) > 1;

-- Check for concurrent writes
SELECT pid, query, state
FROM pg_stat_activity
WHERE query LIKE '%INSERT INTO gsc.search_analytics%'
AND state = 'active';
```

**Solutions:**
1. Add unique constraints if missing
2. Deduplicate existing data:
```sql
DELETE FROM gsc.search_analytics a
USING gsc.search_analytics b
WHERE a.ctid < b.ctid
AND a.property = b.property
AND a.date = b.date
AND a.page = b.page
AND a.query = b.query;
```
3. Fix ingestion logic to prevent duplicates
4. Implement idempotent upsert operations

**Prevention:**
```sql
-- Add unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_search_analytics_unique
ON gsc.search_analytics (property, date, page, query, country, device);
```

---

### 6. Monitoring & Alerting Issues

#### Issue: Alerts Not Firing

**Symptoms:**
- No alerts received despite issues
- Alert fatigue from false positives
- Critical issues not detected

**Diagnosis:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Test alert rules
promtool check rules prometheus/alerts.yml

# Verify alert manager
curl http://localhost:9093/api/v2/alerts
```

**Solutions:**
1. Review alert rule syntax
2. Check alert manager configuration
3. Verify notification channels
4. Test alert delivery manually
5. Adjust alert thresholds

**Prevention:**
- Regular alert testing
- Document alert response procedures
- Review and tune alert thresholds monthly

---

## Emergency Procedures

### System Down

1. Check all services:
```bash
./health-check.sh
systemctl status postgresql
systemctl status prometheus
```

2. Review recent logs:
```bash
tail -100 /var/log/gsc-warehouse/app.log
journalctl -u gsc-warehouse -n 100
```

3. Restart services:
```bash
./stop.sh
./start-collection.sh
```

### Data Corruption

1. Stop all writes immediately
2. Assess damage:
```sql
SELECT * FROM gsc.validate_unified_view_quality();
```
3. Restore from backup:
```bash
./restore.sh --backup <latest-good-backup>
```
4. Verify restoration:
```bash
pytest tests/e2e/test_data_flow.py
```

### Security Incident

1. Isolate affected systems
2. Review access logs
3. Rotate credentials
4. Notify security team
5. Document incident
6. Conduct post-mortem

---

## Getting Help

### Internal Resources
- Documentation: `docs/` directory
- Runbooks: `docs/runbooks/`
- Team Wiki: [Link]

### External Resources
- PostgreSQL: https://www.postgresql.org/docs/
- Google APIs: https://developers.google.com/search-console
- Python asyncio: https://docs.python.org/3/library/asyncio.html

### Escalation
1. Check runbooks first
2. Search internal documentation
3. Contact on-call engineer
4. Escalate to team lead if unresolved in 30 minutes
5. Page senior engineer for critical issues

---

**Document Version**: 1.0
**Last Updated**: 2025-01-14
**Maintained By**: DevOps Team
