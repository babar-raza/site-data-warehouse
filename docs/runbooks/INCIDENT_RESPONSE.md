# Incident Response Runbook

## Overview

This runbook provides step-by-step procedures for responding to production incidents.

## Incident Severity Levels

| Severity | Description | Response Time | Examples |
|----------|-------------|---------------|----------|
| **P0 - Critical** | Complete system outage | Immediate (< 5 min) | Database down, all agents failed |
| **P1 - High** | Major functionality impaired | < 15 minutes | API ingestion failing, multiple agents down |
| **P2 - Medium** | Degraded performance | < 1 hour | Slow queries, single agent failure |
| **P3 - Low** | Minor issues | < 4 hours | Cosmetic issues, non-critical warnings |

## Incident Response Process

### Phase 1: Detection & Alert (0-5 minutes)

#### 1.1 Incident Notification Received

When you receive an alert:

1. **Acknowledge** the alert immediately
2. **Assess** severity based on alert content
3. **Escalate** if P0/P1 severity

```bash
# Quick system status check
./health-check.sh

# Check alert details
curl -s http://localhost:9093/api/v2/alerts | jq '.'
```

#### 1.2 Initial Assessment

Determine:
- What is broken?
- Who is impacted?
- What is the scope?
- What is the severity?

### Phase 2: Triage & Containment (5-15 minutes)

#### 2.1 Establish Incident Channel

**For P0/P1 incidents:**

1. Create incident channel: `#incident-YYYYMMDD-HHMM`
2. Post initial status update
3. @mention on-call team
4. Start incident timeline

#### 2.2 Gather Information

```bash
# System health snapshot
./scripts/incident_snapshot.sh > /tmp/incident_$(date +%Y%m%d_%H%M%S).txt

# Check recent changes
git log --since="24 hours ago" --oneline

# Review recent deployments
cat /var/log/deployments.log | tail -20
```

#### 2.3 Containment Actions

Based on incident type, take immediate containment actions:

---

## Incident Playbooks

### P0: Complete System Outage

#### Symptoms
- Health check fails completely
- No agents running
- Database unreachable
- No data collection

#### Response

**Step 1: Assess Scope (2 min)**

```bash
# Check all services
systemctl status postgresql
systemctl status prometheus
systemctl status gsc-warehouse

# Check system resources
df -h
free -h
uptime
```

**Step 2: Database Recovery (5 min)**

```bash
# If database is down
sudo systemctl start postgresql

# Verify connectivity
psql -U gsc_user -d gsc_warehouse -c "SELECT 1;"

# Check for corruption
psql -U gsc_user -d gsc_warehouse -c "SELECT * FROM pg_stat_activity;"
```

**Step 3: Service Recovery (5 min)**

```bash
# Restart all services
./stop.sh
./start-collection.sh

# Verify agents
./health-check.sh
```

**Step 4: Verify Recovery (3 min)**

```bash
# Run integration test
pytest tests/e2e/test_full_pipeline.py -v -k "test_gsc_ingestion_stage"

# Check data flow
psql -U gsc_user -d gsc_warehouse -c "
SELECT MAX(date) as latest_data FROM gsc.search_analytics;
"
```

---

### P1: Data Ingestion Failure

#### Symptoms
- No new data for > 12 hours
- API errors in logs
- Ingestion jobs failing

#### Response

**Step 1: Check API Status (2 min)**

```bash
# Test GSC API
python -c "
from ingestors.api.gsc_api_ingestor import GSCAPIIngestor
ingestor = GSCAPIIngestor(
    os.getenv('GSC_PROPERTY_URL'),
    os.getenv('GSC_CREDENTIALS_FILE'),
    {}
)
print(ingestor.test_connection())
"

# Check API quota
gcloud logging read "resource.type=api AND severity>=ERROR" --limit 50
```

**Step 2: Identify Root Cause (5 min)**

Common causes:
1. **Expired credentials** → Refresh credentials
2. **Rate limit exceeded** → Wait and retry
3. **API outage** → Check Google status page
4. **Permission revoked** → Verify access in GSC console

**Step 3: Implement Fix (10 min)**

For expired credentials:
```bash
# Update credentials
cp new-credentials.json /etc/gsc-warehouse/credentials/
./validate-setup.sh

# Restart ingestion
./start-collection.sh --days 1
```

For rate limits:
```bash
# Reduce frequency temporarily
export RATE_LIMIT_CALLS_PER_MINUTE=50

# Resume collection
./start-collection.sh --days 1 --rate-limit 50
```

**Step 4: Backfill Missing Data (15 min)**

```bash
# Identify gap
psql -U gsc_user -d gsc_warehouse -c "
SELECT generate_series(
    (SELECT MAX(date) FROM gsc.search_analytics),
    CURRENT_DATE,
    INTERVAL '1 day'
) AS missing_date;
"

# Backfill
./start-collection.sh --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

---

### P1: Agent Orchestration Failure

#### Symptoms
- Multiple agents in ERROR state
- Message bus congestion
- No findings generated

#### Response

**Step 1: Check Agent Status (2 min)**

```bash
# List all agents
ps aux | grep "python.*agent"

# Check agent health
python -c "
from agents.base.agent_registry import AgentRegistry
registry = AgentRegistry()
for agent in registry.get_all_agents():
    print(f'{agent.agent_id}: {agent.status.value}')
"
```

**Step 2: Review Agent Logs (5 min)**

```bash
# Check for errors
grep -i "error\|exception\|failed" logs/agents/*.log | tail -50

# Check message bus
ls -lh data/messages/dead_letters/ | wc -l
```

**Step 3: Restart Affected Agents (5 min)**

```bash
# Stop all agents gracefully
./stop.sh

# Clear dead letters if excessive (> 1000)
if [ $(ls data/messages/dead_letters/ | wc -l) -gt 1000 ]; then
    mv data/messages/dead_letters data/messages/dead_letters_backup_$(date +%Y%m%d)
    mkdir data/messages/dead_letters
fi

# Restart agents
./bootstrap.py --mode production

# Verify
./health-check.sh
```

**Step 4: Monitor Recovery (5 min)**

```bash
# Watch agent activity
watch -n 5 "psql -U gsc_user -d gsc_warehouse -c \"
SELECT agent_id, COUNT(*) as findings, MAX(detected_at) as last_activity
FROM gsc.findings
WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '10 minutes'
GROUP BY agent_id;
\""
```

---

### P1: Database Performance Degradation

#### Symptoms
- Queries taking > 10 seconds
- High database CPU/memory
- Connection pool exhausted

#### Response

**Step 1: Identify Blocking Queries (2 min)**

```sql
-- Find long-running queries
SELECT 
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query,
    state
FROM pg_stat_activity
WHERE state != 'idle'
AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC
LIMIT 10;
```

**Step 2: Kill Problematic Queries (3 min)**

```sql
-- Kill specific query if needed
SELECT pg_terminate_backend(PID);

-- Or cancel instead of kill
SELECT pg_cancel_backend(PID);
```

**Step 3: Check for Lock Contention (2 min)**

```sql
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

**Step 4: Emergency Maintenance (10 min)**

```sql
-- Quick vacuum if needed
VACUUM (ANALYZE, VERBOSE) gsc.search_analytics;

-- Update statistics
ANALYZE gsc.search_analytics;
ANALYZE ga4.page_metrics;

-- Reindex if corruption suspected
REINDEX TABLE CONCURRENTLY gsc.search_analytics;
```

**Step 5: Scale Resources (15 min)**

If issue persists:
```bash
# Increase connection pool temporarily
# Edit .env:
# WAREHOUSE_MAX_CONNECTIONS=200

# Restart services
./stop.sh
./start-collection.sh

# Monitor improvement
watch -n 5 'psql -U gsc_user -d gsc_warehouse -c "
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
"'
```

---

### P2: Single Agent Failure

#### Symptoms
- One agent in ERROR state
- Agent not processing data
- Agent restart loop

#### Response

**Step 1: Isolate Agent (2 min)**

```bash
# Find agent process
ps aux | grep "watcher_001"

# Kill if stuck
kill -9 <PID>

# Check agent logs
tail -100 logs/agents/watcher_001.log
```

**Step 2: Diagnose Issue (5 min)**

Common causes:
1. **Memory leak** → Check memory usage
2. **Database connection** → Test connectivity
3. **Configuration error** → Validate config
4. **Code bug** → Check recent changes

**Step 3: Restart Agent (3 min)**

```bash
# Restart specific agent
python agents/watcher/watcher_agent.py --agent-id watcher_001 &

# Verify started
sleep 5
ps aux | grep "watcher_001"
```

**Step 4: Monitor (5 min)**

```bash
# Watch agent activity
tail -f logs/agents/watcher_001.log

# Check for findings
psql -U gsc_user -d gsc_warehouse -c "
SELECT COUNT(*) FROM gsc.findings 
WHERE agent_id = 'watcher_001' 
AND detected_at >= CURRENT_TIMESTAMP - INTERVAL '5 minutes';
"
```

---

### P2: Disk Space Critical

#### Symptoms
- Disk usage > 90%
- Write failures
- "No space left on device" errors

#### Response

**Step 1: Identify Space Usage (2 min)**

```bash
# Check disk usage
df -h

# Find large files
du -h /var/log/gsc-warehouse | sort -rh | head -20
du -h /opt/gsc-warehouse/data | sort -rh | head -20
```

**Step 2: Emergency Cleanup (5 min)**

```bash
# Clean old logs
find /var/log/gsc-warehouse -type f -mtime +7 -delete

# Clean old backups
find /backups/gsc-warehouse -type f -mtime +30 -delete

# Clean temporary files
rm -rf /tmp/gsc-warehouse-*

# Clean old messages
find data/messages -type f -mtime +7 -delete
```

**Step 3: Archive Data (10 min)**

```bash
# Archive old data to cheaper storage
./scripts/archive_old_data.sh --older-than 180

# Vacuum database
psql -U gsc_user -d gsc_warehouse -c "VACUUM FULL;"
```

**Step 4: Plan Expansion (After incident)**

- Identify growth rate
- Plan storage expansion
- Implement data lifecycle policy

---

## Communication Templates

### Initial Alert

```
🚨 INCIDENT ALERT - P[0/1/2/3]

Title: [Brief description]
Status: Investigating
Impact: [Who/what is affected]
Started: [Timestamp]

Current Actions:
- [Action 1]
- [Action 2]

Next Update: [Time]
Incident Channel: #incident-YYYYMMDD-HHMM
```

### Status Update

```
📊 INCIDENT UPDATE

Title: [Brief description]
Status: [Investigating/Identified/Monitoring/Resolved]
Duration: [Time since start]

What we know:
- [Finding 1]
- [Finding 2]

What we're doing:
- [Action 1]
- [Action 2]

Impact: [Current impact]
ETA: [Estimated resolution time]
Next Update: [Time]
```

### Resolution

```
✅ INCIDENT RESOLVED

Title: [Brief description]
Duration: [Total time]
Impact: [Summary of impact]

Root Cause:
[Brief explanation]

Resolution:
[What was done to fix it]

Prevention:
[Actions to prevent recurrence]

Post-Mortem: [Link to document]
```

---

## Post-Incident Tasks

### Immediate (Within 1 hour)

- [ ] Verify full system recovery
- [ ] Document timeline in incident channel
- [ ] Notify stakeholders of resolution
- [ ] Schedule post-mortem meeting

### Short-term (Within 24 hours)

- [ ] Complete incident report
- [ ] Identify root cause
- [ ] Document lessons learned
- [ ] Update runbooks if needed

### Long-term (Within 1 week)

- [ ] Implement preventive measures
- [ ] Add monitoring/alerts if needed
- [ ] Conduct post-mortem meeting
- [ ] Share learnings with team

---

## Escalation Matrix

| Level | Role | When to Escalate | Contact |
|-------|------|------------------|---------|
| L1 | On-Call Engineer | Immediate response | [Phone] |
| L2 | Team Lead | After 30 min unresolved | [Phone] |
| L3 | Engineering Manager | P0/P1 > 1 hour | [Phone] |
| L4 | Director of Engineering | Major incident | [Phone] |
| L5 | CTO | Business-critical outage | [Phone] |

---

## Incident Report Template

```markdown
# Incident Report: [Title]

## Overview
- **Incident ID**: INC-YYYYMMDD-###
- **Severity**: P[0/1/2/3]
- **Duration**: [Start] to [End]
- **Impact**: [Description]

## Timeline
| Time | Event |
|------|-------|
| HH:MM | Incident detected |
| HH:MM | Investigation began |
| HH:MM | Root cause identified |
| HH:MM | Fix implemented |
| HH:MM | Incident resolved |

## Root Cause
[Detailed explanation]

## Resolution
[What was done to fix]

## Impact Assessment
- **Users Affected**: [Number/Description]
- **Data Loss**: [Yes/No - Details]
- **Downtime**: [Duration]
- **Revenue Impact**: [If applicable]

## Action Items
- [ ] [Preventive measure 1]
- [ ] [Preventive measure 2]
- [ ] [Documentation update]
- [ ] [Monitoring improvement]

## Lessons Learned
- What went well
- What could be improved
- Changes to implement
```

---

**Runbook Version**: 1.0
**Last Updated**: 2025-01-14
**Next Review**: After each major incident
**Owner**: Operations Team
