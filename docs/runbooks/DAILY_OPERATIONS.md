# Daily Operations Runbook

## Overview

This runbook covers routine daily operations for the GSC Warehouse system.

## Daily Health Check (15 minutes)

### Morning Routine (Start of Business Day)

#### 1. System Status Check (5 min)

```bash
# Run automated health check
./health-check.sh

# Expected output:
# ✓ Database: Connected
# ✓ API Access: Valid
# ✓ Agents: 10/10 Running
# ✓ Data Freshness: < 24 hours
# ✓ Disk Space: 45% used
```

**If any check fails, see [Troubleshooting](#troubleshooting) section**

#### 2. Review Overnight Activity (5 min)

```bash
# Check data collection status
psql -U gsc_user -d gsc_warehouse -c "
SELECT 
    MAX(date) as latest_data,
    COUNT(*) as records_today,
    COUNT(DISTINCT page) as unique_pages
FROM gsc.search_analytics 
WHERE date >= CURRENT_DATE - INTERVAL '1 day';
"

# Check agent activity
psql -U gsc_user -d gsc_warehouse -c "
SELECT 
    agent_id,
    COUNT(*) as findings,
    MAX(detected_at) as last_activity
FROM gsc.findings
WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
GROUP BY agent_id;
"
```

**Expected Values:**
- Latest data: Yesterday's date
- Records today: > 10,000
- Unique pages: > 100
- Agent findings: 5-50 per agent

#### 3. Alert Review (5 min)

```bash
# Check for active alerts
curl -s http://localhost:9093/api/v2/alerts | jq '.[] | select(.status.state=="active")'

# Review error logs
grep -i "error\|critical\|fatal" /var/log/gsc-warehouse/app.log | tail -20
```

**Action Required:**
- Address any CRITICAL alerts immediately
- Document HIGH priority alerts for team review
- Monitor MEDIUM alerts for trends

---

## Weekly Tasks

### Monday: Planning & Review (30 min)

#### 1. Weekly Performance Review

```bash
# Generate weekly report
python scripts/weekly_report.py --output reports/weekly_$(date +%Y%m%d).html

# Review key metrics:
# - Data completeness: Should be > 95%
# - Agent performance: Average processing time
# - Error rate: Should be < 1%
# - Recommendation success rate: > 80%
```

#### 2. Capacity Planning

```bash
# Check growth trends
psql -U gsc_user -d gsc_warehouse -c "
SELECT 
    DATE_TRUNC('week', date) as week,
    COUNT(*) as weekly_records,
    pg_size_pretty(pg_total_relation_size('gsc.search_analytics')) as table_size
FROM gsc.search_analytics
WHERE date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY week
ORDER BY week DESC;
"
```

**Action Items:**
- If growth > 50% MoM, plan capacity increase
- If disk space > 70%, add storage
- Review agent scaling needs

### Tuesday: Security Review (20 min)

#### 1. Credential Audit

```bash
# Check credential expiration
python scripts/check_credentials.py

# Expected output:
# ✓ GSC credentials: Valid until 2025-06-01
# ✓ GA4 credentials: Valid until 2025-06-01
# ✓ Database password: Last changed 45 days ago
```

#### 2. Access Review

```bash
# Review database connections
psql -U gsc_user -d gsc_warehouse -c "
SELECT DISTINCT usename, application_name, client_addr
FROM pg_stat_activity
WHERE datname = 'gsc_warehouse';
"
```

**Action Required:**
- Rotate credentials if > 90 days old
- Remove unauthorized access
- Document any new service accounts

### Wednesday: Performance Optimization (30 min)

#### 1. Database Maintenance

```bash
# Vacuum and analyze
psql -U gsc_user -d gsc_warehouse -c "
VACUUM ANALYZE gsc.search_analytics;
VACUUM ANALYZE ga4.page_metrics;
VACUUM ANALYZE gsc.findings;
VACUUM ANALYZE gsc.recommendations;
"

# Check for bloat
psql -U gsc_user -d gsc_warehouse -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    n_dead_tup
FROM pg_stat_user_tables
WHERE schemaname IN ('gsc', 'ga4')
ORDER BY n_dead_tup DESC;
"
```

#### 2. Query Performance Review

```bash
# Identify slow queries
psql -U gsc_user -d gsc_warehouse -c "
SELECT 
    query,
    calls,
    mean_exec_time,
    stddev_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 1000
ORDER BY mean_exec_time DESC
LIMIT 10;
"
```

**Action Items:**
- Optimize queries with mean_exec_time > 1s
- Add indexes where beneficial
- Update query documentation

### Thursday: Backup Verification (15 min)

#### 1. Backup Status

```bash
# List recent backups
ls -lht /backups/gsc-warehouse/ | head -10

# Verify latest backup
./scripts/verify_backup.sh $(ls -t /backups/gsc-warehouse/ | head -1)
```

#### 2. Test Recovery (Monthly)

```bash
# On first Thursday of month, test recovery
./restore.sh --backup <backup-id> --test-mode --target /tmp/recovery_test
```

**Success Criteria:**
- Backup size reasonable (± 20% of previous)
- Backup integrity check passes
- Test recovery completes without errors

### Friday: Week Close & Planning (20 min)

#### 1. Generate Weekly Summary

```bash
# Create summary report
python scripts/weekly_summary.py > reports/summary_$(date +%Y%m%d).txt

# Email to team
cat reports/summary_$(date +%Y%m%d).txt | mail -s "GSC Warehouse Weekly Summary" team@example.com
```

#### 2. Update Documentation

- [ ] Update any changed procedures
- [ ] Document any issues encountered
- [ ] Update capacity forecasts
- [ ] Plan next week's priorities

---

## Monthly Tasks

### First Monday: Monthly Review (1 hour)

#### 1. System Audit

```bash
# Full system health report
python scripts/monthly_audit.py --comprehensive

# Review:
# - Data quality trends
# - System performance
# - Cost analysis
# - Capacity forecasts
```

#### 2. Dependency Updates

```bash
# Check for updates
pip list --outdated

# Review security advisories
python -m safety check
```

**Action Items:**
- Plan dependency upgrades
- Schedule maintenance window
- Test updates in staging first

#### 3. Incident Review

- Review all incidents from past month
- Update runbooks based on lessons learned
- Implement preventive measures
- Document post-mortems

### Third Thursday: Disaster Recovery Test (2 hours)

#### 1. Full Recovery Drill

```bash
# Simulate complete failure
./scripts/dr_drill.sh --full-test

# Verify:
# - Backup restoration works
# - All services start correctly
# - Data integrity maintained
# - Agents function properly
```

#### 2. Update DR Plan

- Document any issues found
- Update recovery procedures
- Verify contact information current
- Test escalation procedures

---

## Scheduled Maintenance Windows

### Weekly Maintenance (Sunday 2:00 AM - 4:00 AM)

#### Tasks
1. Database vacuum and analyze
2. Log rotation and cleanup
3. Temporary file cleanup
4. Index maintenance
5. View refresh optimization

#### Execution

```bash
# Pre-maintenance
./scripts/pre_maintenance.sh

# Maintenance
./scripts/weekly_maintenance.sh

# Post-maintenance
./scripts/post_maintenance.sh
./health-check.sh
```

### Monthly Maintenance (First Sunday 2:00 AM - 6:00 AM)

#### Tasks
1. Full database reindex
2. System updates and patching
3. Dependency updates
4. Configuration review
5. Performance tuning

---

## Routine Monitoring Tasks

### Every Hour

```bash
# Automated via cron
0 * * * * /opt/gsc-warehouse/scripts/hourly_check.sh
```

Checks:
- Agent health status
- Data ingestion progress
- Error rate
- System resources

### Every 4 Hours

```bash
# Automated via cron
0 */4 * * * /opt/gsc-warehouse/scripts/data_collection.sh
```

Tasks:
- Trigger data ingestion
- Refresh materialized views
- Update statistics

### Every 6 Hours

```bash
# Automated via cron
0 */6 * * * /opt/gsc-warehouse/backup.sh
```

Tasks:
- Create incremental backup
- Verify backup integrity
- Cleanup old backups (> 30 days)

---

## Common Operations

### Restart Agents

```bash
# Graceful restart
./stop.sh
sleep 10
./bootstrap.py --mode production

# Verify agents started
python -c "
from agents.base.agent_registry import AgentRegistry
registry = AgentRegistry()
print(f'Active agents: {len(registry.get_all_agents())}')
"
```

### Manual Data Collection

```bash
# Collect specific date range
python start-collection.sh --start-date 2024-01-01 --end-date 2024-01-07

# Collect yesterday's data
python start-collection.sh --days 1
```

### Force View Refresh

```bash
# Refresh all views
python warehouse/refresh_views.py --view all

# Refresh specific view
python warehouse/refresh_views.py --view unified_page_performance

# With validation
python warehouse/refresh_views.py --view all --validate
```

### Clear Agent State

```bash
# Clear stuck agent state
rm -rf data/agent_state/*

# Clear message queue
rm -rf data/messages/*

# Restart agents
./stop.sh && ./bootstrap.py
```

---

## Quality Checks

### Data Quality Validation

```bash
# Run daily at 9:00 AM
python scripts/validate_data_quality.py

# Check for:
# - Missing data
# - Duplicate records
# - Anomalous values
# - Referential integrity
```

### Agent Performance Check

```bash
# Review agent metrics
python scripts/agent_performance.py --last 24h

# Expected ranges:
# - Watcher: < 5 min processing
# - Diagnostician: < 10 min processing
# - Strategist: < 15 min processing
# - Dispatcher: < 20 min processing
```

---

## Troubleshooting

### System Unresponsive

1. Check system resources:
```bash
top
df -h
free -h
```

2. Review logs:
```bash
tail -f /var/log/gsc-warehouse/app.log
journalctl -u gsc-warehouse -f
```

3. Restart services if needed:
```bash
./stop.sh
./start-collection.sh
```

### Data Not Updating

1. Check ingestion status:
```bash
grep "ingestion" /var/log/gsc-warehouse/app.log | tail -20
```

2. Verify API access:
```bash
python validate-setup.sh
```

3. Manual trigger:
```bash
python start-collection.sh --days 1
```

### Alerts Not Clearing

1. Verify issue resolved
2. Check alert rules
3. Restart alert manager if needed:
```bash
systemctl restart alertmanager
```

---

## Handoff Checklist

When handing off on-call:

- [ ] Review current alerts
- [ ] Document any ongoing issues
- [ ] Share access credentials securely
- [ ] Brief on any scheduled maintenance
- [ ] Provide escalation contacts
- [ ] Review recent changes

---

## Contact Information

### On-Call Rotation
- Primary: [Name] - [Phone] - [Email]
- Secondary: [Name] - [Phone] - [Email]
- Escalation: [Manager] - [Phone] - [Email]

### Vendors
- Database Support: [Contact Info]
- Cloud Provider: [Contact Info]
- Monitoring: [Contact Info]

---

**Runbook Version**: 1.0
**Last Updated**: 2025-01-14
**Next Review**: Monthly
**Owner**: Operations Team
