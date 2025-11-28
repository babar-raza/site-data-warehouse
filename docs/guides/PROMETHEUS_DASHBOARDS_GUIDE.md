# Prometheus Dashboards Guide

**Complete guide to Grafana dashboards for Prometheus metrics monitoring**

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Dashboard Catalog](#dashboard-catalog)
4. [Common Tasks](#common-tasks)
5. [Troubleshooting](#troubleshooting)
6. [PromQL Query Reference](#promql-query-reference)
7. [Customization Guide](#customization-guide)

---

## Overview

The GSC Warehouse monitoring system includes **5 pre-built Grafana dashboards** that visualize Prometheus metrics across your entire infrastructure:

- **Infrastructure Overview** - Container metrics (CPU, memory, network, disk)
- **Database Performance** - PostgreSQL metrics (connections, queries, cache)
- **Application Metrics** - Custom application and Redis metrics
- **Service Health** - Real-time service status and health checks
- **Alert Status** - Alert management and monitoring system health

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         GRAFANA                             │
│                    (http://localhost:3000)                   │
│                                                             │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Infrastructure│  │   Database   │  │   Application   │ │
│  │   Overview    │  │  Performance │  │     Metrics     │ │
│  └───────────────┘  └──────────────┘  └─────────────────┘ │
│  ┌───────────────┐  ┌──────────────┐                      │
│  │    Service    │  │    Alert     │                      │
│  │    Health     │  │    Status    │                      │
│  └───────────────┘  └──────────────┘                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  PROMETHEUS   │
                   │  (port 9090)  │
                   └───────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    ┌─────────┐    ┌─────────────┐  ┌──────────────┐
    │cAdvisor │    │PostgreSQL   │  │    Redis     │
    │         │    │ Exporter    │  │  Exporter    │
    └─────────┘    └─────────────┘  └──────────────┘
```

---

## Quick Start

### Accessing Dashboards

1. **Open Grafana**
   - URL: http://localhost:3000
   - Default credentials: `admin` / `admin`
   - Change password on first login (recommended)

2. **Navigate to Dashboards**
   - Click **Dashboards** icon (四 squares) in left sidebar
   - OR click **Search** (magnifying glass) and browse

3. **Available Dashboards**
   - Infrastructure Overview
   - Database Performance
   - Application Metrics
   - Service Health
   - Alert Status

### First-Time Setup Checklist

- [ ] All Docker containers running (`docker-compose ps`)
- [ ] Prometheus accessible at http://localhost:9090
- [ ] Grafana accessible at http://localhost:3000
- [ ] All Prometheus targets UP (http://localhost:9090/targets)
- [ ] Dashboards visible in Grafana
- [ ] Panels showing data (not "No Data")

---

## Dashboard Catalog

### 1. Infrastructure Overview

**Purpose:** Monitor Docker container resource usage and performance

**Access:** Dashboards → Infrastructure Overview

**Refresh Rate:** 30 seconds

**Key Metrics:**
- System uptime
- Active containers count
- Total memory usage (all containers)
- Total CPU usage (all containers)
- Per-container CPU usage
- Per-container memory usage
- Network traffic (RX/TX)
- Disk I/O (read/write)
- Container status table

**When to Use:**
- Daily health checks
- Capacity planning
- Performance troubleshooting
- Resource optimization

**Key Insights:**
- **High CPU:** Identify which containers need optimization
- **High Memory:** Detect memory leaks or under-provisioned limits
- **Network Spikes:** Correlate with application events
- **Restarts:** Check container status table for stability issues

---

### 2. Database Performance

**Purpose:** Monitor PostgreSQL database health and performance

**Access:** Dashboards → Database Performance

**Refresh Rate:** 30 seconds

**Key Metrics:**
- Active connections
- Transactions per second (commits/rollbacks)
- Cache hit ratio
- Database size
- Connections by database
- Transaction rate trends
- Rows fetched vs returned
- Rows modified (insert/update/delete)
- Deadlocks
- Disk blocks (read vs cache hit)
- Database statistics table

**When to Use:**
- Database performance tuning
- Connection pool monitoring
- Query optimization
- Capacity planning

**Key Insights:**
- **Cache Hit Ratio <95%:** Consider increasing `shared_buffers`
- **High Connections:** Check for connection leaks
- **Deadlocks >0:** Review transaction locking patterns
- **High Rollback Rate:** Investigate application errors

**Optimization Tips:**
```sql
-- Check current shared_buffers
SHOW shared_buffers;

-- Recommended: 25% of system RAM
-- Example: For 8GB RAM, set shared_buffers = 2GB
ALTER SYSTEM SET shared_buffers = '2GB';
```

---

### 3. Application Metrics

**Purpose:** Monitor application-specific and Redis cache metrics

**Access:** Dashboards → Application Metrics

**Refresh Rate:** 30 seconds

**Key Metrics:**
- GSC data freshness (hours since last update)
- Total rows (GSC data)
- Collection status (success/failure)
- Metrics exporter uptime
- Redis memory usage
- Redis connected clients
- Redis commands per second
- Redis hit rate
- GSC data growth trends
- Collection latency
- Prometheus target status table

**When to Use:**
- Application health monitoring
- Data pipeline validation
- Cache performance tuning
- Service dependency tracking

**Key Insights:**
- **Data Freshness >24h:** Ingestion pipeline issue
- **Collection Status = 0:** Last collection failed
- **Redis Hit Rate <80%:** Cache strategy needs review
- **High Collection Latency:** API rate limiting or network issues

---

### 4. Service Health

**Purpose:** Real-time service availability and health monitoring

**Access:** Dashboards → Service Health

**Refresh Rate:** 10 seconds (real-time)

**Key Metrics:**
- Services UP count
- Services DOWN count
- Container restarts (last hour)
- Average response time
- Service status timeline
- CPU usage by service
- Memory usage by service
- Scrape duration by target
- Failed scrapes
- Health check details table

**When to Use:**
- Incident response
- Service availability monitoring
- SLA tracking
- On-call dashboard (monitor display)

**Key Insights:**
- **Services DOWN >0:** Immediate investigation required
- **Frequent Restarts:** Container instability
- **High Scrape Duration:** Slow exporter or network issues
- **Failed Scrapes:** Data quality problems

**Incident Response Flow:**
1. Check **Services DOWN** stat
2. Review **Service Status Timeline** for when failure started
3. Check **Health Check Details** table for specific target
4. Investigate container logs: `docker logs <container_name>`

---

### 5. Alert Status

**Purpose:** Monitor alerting system and manage active alerts

**Access:** Dashboards → Alert Status

**Refresh Rate:** 30 seconds

**Key Metrics:**
- Active alerts count
- Pending alerts count
- Critical alerts count
- Warning alerts count
- Alert firing timeline
- Alert count by severity
- Alert evaluation duration
- Alert rule evaluations
- Alert rule failures
- Active alert details table

**When to Use:**
- Alert triage and prioritization
- Alerting system health checks
- Alert rule performance tuning
- Incident management

**Key Insights:**
- **Active Alerts >0:** Investigate immediately
- **Pending Alerts >0:** Alerts about to fire (early warning)
- **Alert Rule Failures >0:** Alert configuration issue
- **High Evaluation Duration:** Optimize alert queries

**Alert Priority:**
1. **Critical Alerts** - Immediate response (24/7)
2. **Warning Alerts** - Response within business hours
3. **Info Alerts** - Review during normal operations

---

## Common Tasks

### Task 1: Check System Health

**Steps:**
1. Open **Service Health** dashboard
2. Verify **Services UP** >= 5
3. Verify **Services DOWN** = 0
4. Check **Container Restarts** < 3 in last hour
5. Review **Health Check Details** table

**Expected Results:**
- All services showing ✅ UP
- No excessive restarts
- Response times < 1 second

### Task 2: Investigate High Memory Usage

**Steps:**
1. Open **Infrastructure Overview** dashboard
2. Check **Total Memory Usage** stat
3. Review **Container Memory Usage by Service** graph
4. Identify container(s) with highest memory
5. Click container name in legend to isolate line
6. Check if memory trending upward (memory leak)

**Actions:**
- If steady: Normal operation
- If trending up: Investigate container logs
- If >90% of limit: Consider increasing memory limit

### Task 3: Optimize Database Performance

**Steps:**
1. Open **Database Performance** dashboard
2. Check **Cache Hit Ratio**
   - <90%: Increase `shared_buffers`
   - >95%: Cache is optimal
3. Check **Active Connections**
   - >80%: Investigate connection leaks
   - Use: `SELECT * FROM pg_stat_activity;`
4. Check **Transaction Rate**
   - High rollback rate: Application errors
5. Check **Deadlocks** panel
   - >0: Review locking patterns

### Task 4: Troubleshoot Collection Failures

**Steps:**
1. Open **Application Metrics** dashboard
2. Check **Collection Status** stat
   - 0 = Failed, 1 = Success
3. If failed, check **Collection Latency** for timeouts
4. Check **Data Freshness** (hours since last successful collection)
5. Investigate metrics_exporter logs:
   ```bash
   docker logs gsc_metrics_exporter --tail 100
   ```

### Task 5: Review Active Alerts

**Steps:**
1. Open **Alert Status** dashboard
2. Check **Active Alerts** stat
3. Review **Active Alert Details** table
   - Sort by severity (critical first)
4. Click alert name for details
5. Follow runbook for specific alert
6. Mark alert as acknowledged (if using Alertmanager)

---

## Troubleshooting

### Problem: Dashboard shows "No Data"

**Possible Causes:**
1. Prometheus not scraping target
2. Exporter not running
3. Time range too narrow
4. Metric name changed

**Solutions:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'

# Check if exporter is running
docker ps | grep exporter

# Check exporter metrics endpoint
curl http://localhost:9187/metrics  # postgres
curl http://localhost:9121/metrics  # redis
curl http://localhost:8003/metrics  # docker_stats_exporter

# Restart Prometheus
docker restart gsc_prometheus
```

### Problem: Panel shows "Error" or "Bad Gateway"

**Cause:** Prometheus datasource not configured or unreachable

**Solution:**
1. Go to Configuration → Data Sources
2. Click "Prometheus"
3. Verify URL: `http://prometheus:9090`
4. Click "Save & Test"
5. Should show: "Data source is working"

### Problem: Metrics stopped updating

**Cause:** Scrape target is down or timing out

**Solution:**
1. Check Prometheus targets page: http://localhost:9090/targets
2. Find target with status "DOWN" or "UNKNOWN"
3. Check container health:
   ```bash
   docker ps -a  # Check if container is running
   docker logs <container_name>  # Check for errors
   ```
4. Restart container if needed:
   ```bash
   docker restart <container_name>
   ```

### Problem: Dashboard loads slowly

**Possible Causes:**
1. Too many time series
2. Large time range
3. Heavy PromQL queries

**Solutions:**
- Reduce time range (use "Last 1 hour" instead of "Last 24 hours")
- Increase refresh interval (30s → 1m)
- Optimize PromQL queries (use recording rules)
- Reduce panel count (hide unnecessary panels)

### Problem: Alert not firing despite condition met

**Possible Causes:**
1. Alert `for` duration not elapsed
2. Alert rule syntax error
3. Prometheus not evaluating rules

**Solutions:**
```bash
# Check alert rules loaded
curl http://localhost:9090/api/v1/rules | jq '.data.groups[] | .name'

# Validate alert rule syntax
docker exec gsc_prometheus promtool check rules /etc/prometheus/alerts.yml

# Check Prometheus logs
docker logs gsc_prometheus | grep -i alert
```

---

## PromQL Query Reference

### Common Query Patterns

#### Container Metrics (cAdvisor)

**CPU Usage Percentage:**
```promql
# Per container
rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100

# Total across all containers
sum(rate(container_cpu_usage_seconds_total{name!=""}[5m])) * 100
```

**Memory Usage:**
```promql
# Absolute bytes
container_memory_usage_bytes{name!=""}

# Percentage of limit
(container_memory_usage_bytes / container_spec_memory_limit_bytes) * 100
```

**Network Traffic:**
```promql
# Received bytes per second
rate(container_network_receive_bytes_total{name!=""}[5m])

# Transmitted bytes per second
rate(container_network_transmit_bytes_total{name!=""}[5m])
```

#### Database Metrics (PostgreSQL)

**Cache Hit Ratio:**
```promql
sum(pg_stat_database_blks_hit) /
(sum(pg_stat_database_blks_hit) + sum(pg_stat_database_blks_read)) * 100
```

**Connections by Database:**
```promql
pg_stat_database_numbackends{datname!~"template.*|postgres"}
```

**Transaction Rate:**
```promql
# Commits per second
rate(pg_stat_database_xact_commit[5m])

# Rollbacks per second
rate(pg_stat_database_xact_rollback[5m])
```

#### Redis Metrics

**Hit Rate:**
```promql
rate(redis_keyspace_hits_total[5m]) /
(rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m])) * 100
```

**Memory Usage Percentage:**
```promql
redis_memory_used_bytes / redis_memory_max_bytes * 100
```

### PromQL Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `rate()` | Per-second rate over time | `rate(metric[5m])` |
| `sum()` | Aggregate metric values | `sum(metric) by (label)` |
| `avg()` | Average metric values | `avg(metric)` |
| `count()` | Count time series | `count(up == 1)` |
| `increase()` | Total increase over time | `increase(metric[1h])` |

---

## Customization Guide

### Creating Dashboard Variables

Variables allow filtering dashboards by service, container, database, etc.

**Example: Add Container Filter**

1. Open dashboard
2. Click ⚙️ (Settings) → Variables → New
3. Configure:
   - Name: `container`
   - Type: Query
   - Data source: Prometheus
   - Query: `label_values(container_memory_usage_bytes, name)`
   - Refresh: On dashboard load
4. Save dashboard
5. Use in panel query: `container_memory_usage_bytes{name="$container"}`

### Adding Custom Panels

**Example: Add Disk Usage Panel**

1. Edit dashboard
2. Click "Add panel"
3. Configure query:
   ```promql
   (container_fs_usage_bytes / container_fs_limit_bytes) * 100
   ```
4. Set visualization: Time series or Gauge
5. Configure field options:
   - Unit: Percent (0-100)
   - Thresholds: Green 0, Yellow 80, Red 90
6. Save panel

### Modifying Alert Thresholds

**Example: Change Memory Warning Threshold**

1. Edit `prometheus/alerts.yml`:
   ```yaml
   - alert: HighMemoryUsage
     expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) * 100 > 85
     # Changed from 90 to 85
   ```
2. Reload Prometheus:
   ```bash
   docker exec gsc_prometheus curl -X POST http://localhost:9090/-/reload
   ```

### Exporting/Importing Dashboards

**Export Dashboard:**
1. Open dashboard
2. Click ⚙️ → JSON Model
3. Copy JSON
4. Save to file

**Import Dashboard:**
1. Click + → Import
2. Paste JSON or upload file
3. Select Prometheus datasource
4. Click Import

---

## Best Practices

### Dashboard Organization
- **Use folders:** Group related dashboards
- **Naming convention:** Consistent naming (e.g., "GSC - Infrastructure")
- **Tags:** Add tags for easy searching
- **Documentation:** Add panel descriptions

### Query Optimization
- **Use recording rules** for complex queries
- **Limit time ranges** to necessary data
- **Avoid wildcards** in labels when possible
- **Use `rate()` for counters**, not `increase()`

### Alerting Strategy
- **Critical alerts:** Require immediate action
- **Warning alerts:** Investigate within business hours
- **Avoid alert fatigue:** Set appropriate thresholds
- **Use `for` duration:** Prevent flapping

### Monitoring Hygiene
- **Regular reviews:** Weekly dashboard reviews
- **Update thresholds:** As system grows
- **Archive unused dashboards:** Keep catalog clean
- **Document changes:** Use dashboard version history

---

## Additional Resources

### Official Documentation
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Tutorial](https://prometheus.io/docs/prometheus/latest/querying/basics/)

### Exporter Documentation
- [Docker Stats Exporter](../../services/docker_exporter/README.md) - Custom Windows-compatible container metrics exporter
- [PostgreSQL Exporter](https://github.com/prometheus-community/postgres_exporter)
- [Redis Exporter](https://github.com/oliver006/redis_exporter)

### Community Resources
- [Grafana Dashboards](https://grafana.com/grafana/dashboards/) - Pre-built dashboard library
- [Awesome Prometheus](https://github.com/roaldnefs/awesome-prometheus) - Curated list of resources

---

## Getting Help

### Troubleshooting Steps
1. Check this guide's [Troubleshooting](#troubleshooting) section
2. Review Prometheus targets: http://localhost:9090/targets
3. Check container logs: `docker logs <container_name>`
4. Validate configurations: `promtool check config`

### Support Channels
- **Project Documentation:** `docs/` directory
- **Deployment Guide:** `docs/DEPLOYMENT.md`
- **GitHub Issues:** Report bugs or request features

---

**Last Updated:** 2025-11-24
**Version:** 1.0
**Maintained By:** GSC Warehouse Team
