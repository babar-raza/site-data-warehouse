# Prometheus UI Enhancement Plan

## Overview

This plan outlines the implementation of a comprehensive UI-based view for Prometheus metrics, providing visual dashboards similar to what Grafana offers for other data sources.

## Current State

- **Prometheus**: Running on port 9090 with basic built-in web UI
- **Grafana**: Running on port 3000 with 5 pre-built dashboards (SERP, CWV, GA4, GSC, Hybrid)
- **Prometheus UI limitations**:
  - Basic query interface (PromQL)
  - Limited visualization options
  - No pre-built dashboards
  - Not user-friendly for non-technical users

## Goals

1. Provide a visual, user-friendly interface for Prometheus metrics
2. Create pre-built dashboards for system monitoring
3. Enable easy exploration of metrics without writing PromQL queries
4. Match the quality and usability of existing Grafana dashboards

## Implementation Approach

### Option 1: Grafana Dashboards for Prometheus (Recommended)

**Why this is the best approach:**
- Grafana is already running and configured
- Grafana natively supports Prometheus as a data source
- Leverages existing infrastructure
- Consistent UI experience across all monitoring
- Industry-standard solution

**Implementation Steps:**

#### Phase 1: Configure Prometheus Data Source in Grafana

1. **Add Prometheus as a data source**
   - Location: `grafana/provisioning/datasources/prometheus.yml`
   - Already configured but need to verify
   - URL: `http://prometheus:9090`
   - Access: Server (default)

2. **Test connection**
   - Verify Grafana can query Prometheus
   - Test basic PromQL queries
   - Ensure metrics are accessible

#### Phase 2: Create System Monitoring Dashboards

1. **Infrastructure Overview Dashboard**
   ```
   File: grafana/provisioning/dashboards/infrastructure-overview.json

   Panels:
   - System uptime
   - Container CPU usage (all services)
   - Container memory usage (all services)
   - Disk I/O
   - Network traffic
   - Container health status
   ```

2. **Database Performance Dashboard**
   ```
   File: grafana/provisioning/dashboards/database-performance.json

   Panels:
   - PostgreSQL connections (active, idle, total)
   - Query execution time
   - Transaction rate
   - Cache hit ratio
   - Table sizes
   - Index usage
   - Slow queries (>1s)
   - Locks and deadlocks
   ```

3. **Application Metrics Dashboard**
   ```
   File: grafana/provisioning/dashboards/application-metrics.json

   Panels:
   - Custom metrics from metrics_exporter
   - API request rates
   - Task queue length (Celery)
   - Task execution times
   - Error rates by service
   - Data collection status
   - Ingestion pipeline health
   ```

4. **Alert Status Dashboard**
   ```
   File: grafana/provisioning/dashboards/alert-status.json

   Panels:
   - Active alerts
   - Alert history (last 24h)
   - Alert rules status
   - Notification delivery status
   - Alert trends
   ```

5. **Service Health Dashboard**
   ```
   File: grafana/provisioning/dashboards/service-health.json

   Panels:
   - All containers status (up/down)
   - Container restart count
   - Health check results
   - Service dependencies map
   - Response times per service
   - Error rates per service
   ```

#### Phase 3: Prometheus Metrics Enhancement

1. **Export additional custom metrics**
   - Enhance `compose/dockerfiles/Dockerfile.metrics`
   - Add application-specific metrics:
     - Data freshness (time since last ingestion)
     - Row counts per table
     - Query performance metrics
     - Anomaly detection results
     - Agent execution metrics
     - Content analysis metrics

2. **Add PostgreSQL Exporter**
   ```yaml
   # Add to docker-compose.yml
   postgres_exporter:
     image: prometheuscommunity/postgres-exporter:latest
     container_name: gsc_postgres_exporter
     environment:
       DATA_SOURCE_NAME: "postgresql://user:pass@warehouse:5432/seo_warehouse?sslmode=disable"
     ports:
       - "9187:9187"
     networks:
       - gsc_network
     depends_on:
       - warehouse
     restart: unless-stopped
   ```

3. **Add Redis Exporter** (for Celery monitoring)
   ```yaml
   redis_exporter:
     image: oliver006/redis_exporter:latest
     container_name: gsc_redis_exporter
     environment:
       REDIS_ADDR: "redis:6379"
     ports:
       - "9121:9121"
     networks:
       - gsc_network
     depends_on:
       - redis
     restart: unless-stopped
   ```

4. **Update Prometheus configuration**
   ```yaml
   # prometheus/prometheus.yml
   scrape_configs:
     - job_name: 'prometheus'
       static_configs:
         - targets: ['localhost:9090']

     - job_name: 'postgres'
       static_configs:
         - targets: ['postgres_exporter:9187']

     - job_name: 'redis'
       static_configs:
         - targets: ['redis_exporter:9121']

     - job_name: 'custom_metrics'
       static_configs:
         - targets: ['metrics_exporter:8002']
   ```

#### Phase 4: Alert Rules Configuration

1. **Create Prometheus alert rules**
   ```yaml
   # prometheus/alerts.yml
   groups:
     - name: infrastructure_alerts
       rules:
         - alert: HighMemoryUsage
           expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
           for: 5m
           labels:
             severity: warning
           annotations:
             summary: "High memory usage on {{ $labels.container_name }}"

         - alert: ContainerDown
           expr: up == 0
           for: 1m
           labels:
             severity: critical
           annotations:
             summary: "Container {{ $labels.job }} is down"

         - alert: DatabaseConnectionsFull
           expr: pg_stat_database_numbackends / pg_settings_max_connections > 0.8
           for: 5m
           labels:
             severity: warning
           annotations:
             summary: "PostgreSQL connections near limit"
   ```

2. **Configure Alertmanager** (optional)
   ```yaml
   # docker-compose.yml
   alertmanager:
     image: prom/alertmanager:latest
     container_name: gsc_alertmanager
     volumes:
       - ./prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml
     ports:
       - "9093:9093"
     networks:
       - gsc_network
     restart: unless-stopped
   ```

#### Phase 5: Documentation and Training

1. **Create user guide**
   - Location: `docs/guides/PROMETHEUS_DASHBOARDS_GUIDE.md`
   - How to access dashboards
   - How to customize panels
   - Common PromQL queries
   - Troubleshooting

2. **Update main documentation**
   - README.md: Add Prometheus dashboards to features
   - DEPLOYMENT.md: Add dashboard access instructions
   - MONITORING_GUIDE.md: Comprehensive monitoring guide

### Option 2: Alternative Prometheus UI Tools (Not Recommended)

These are alternative tools but add complexity without significant benefits over Grafana:

1. **Prometheus UI Alternatives:**
   - PromLens - Query builder UI
   - Thanos - Long-term storage + UI
   - VictoriaMetrics - Prometheus-compatible with better UI

   **Why not recommended:**
   - Additional complexity
   - Grafana already provides superior visualization
   - More maintenance overhead

## Implementation Timeline

### Week 1: Foundation
- ✅ Configure Prometheus data source in Grafana (verify existing)
- ✅ Test connection and basic queries
- 🔲 Create first dashboard (Infrastructure Overview)

### Week 2: Core Dashboards
- 🔲 Database Performance Dashboard
- 🔲 Application Metrics Dashboard
- 🔲 Add PostgreSQL Exporter

### Week 3: Advanced Features
- 🔲 Service Health Dashboard
- 🔲 Alert Status Dashboard
- 🔲 Add Redis Exporter
- 🔲 Configure alert rules

### Week 4: Polish & Documentation
- 🔲 Test all dashboards
- 🔲 Create user documentation
- 🔲 Update deployment scripts
- 🔲 Training materials

## Technical Requirements

### Dependencies
- Grafana (already installed)
- Prometheus (already installed)
- PostgreSQL Exporter (new)
- Redis Exporter (new)

### Configuration Files
```
grafana/
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yml (verify)
│   └── dashboards/
│       ├── infrastructure-overview.json (new)
│       ├── database-performance.json (new)
│       ├── application-metrics.json (new)
│       ├── alert-status.json (new)
│       └── service-health.json (new)

prometheus/
├── prometheus.yml (update)
├── alerts.yml (update)
└── alertmanager.yml (new, optional)
```

### Docker Compose Changes
```yaml
# Add postgres_exporter
# Add redis_exporter
# Add alertmanager (optional)
# Update prometheus config volume mounts
```

## Success Metrics

1. **User Experience**
   - 5 new Prometheus-based Grafana dashboards
   - All system metrics visible in UI
   - No PromQL knowledge required for basic monitoring

2. **Coverage**
   - 100% of critical services monitored
   - Database metrics exported
   - Application metrics exported
   - Alert rules configured

3. **Performance**
   - Dashboard load time < 2 seconds
   - Metric scrape interval: 15 seconds
   - Data retention: 15 days (default)

## Maintenance Plan

### Daily
- Automatic metric collection (Prometheus scrapes)
- Alert evaluation

### Weekly
- Review dashboard performance
- Check for missing metrics

### Monthly
- Update dashboards based on user feedback
- Optimize PromQL queries
- Review alert thresholds

## Rollback Plan

If issues arise:
1. Disable new exporters (postgres, redis)
2. Revert to previous Prometheus configuration
3. Remove new Grafana dashboards
4. All existing functionality remains intact

## Cost Analysis

- **Infrastructure Cost**: $0 (all open-source)
- **Maintenance Time**: ~2 hours/month
- **Initial Setup Time**: ~16 hours (4 weeks part-time)

## Resources

### Official Documentation
- [Grafana Prometheus Integration](https://grafana.com/docs/grafana/latest/datasources/prometheus/)
- [Prometheus Exporters](https://prometheus.io/docs/instrumenting/exporters/)
- [PostgreSQL Exporter](https://github.com/prometheus-community/postgres_exporter)
- [Redis Exporter](https://github.com/oliver006/redis_exporter)

### Example Dashboards
- [Grafana Dashboard Repository](https://grafana.com/grafana/dashboards/)
- [PostgreSQL Dashboard](https://grafana.com/grafana/dashboards/9628)
- [Docker Container Dashboard](https://grafana.com/grafana/dashboards/893)

## Conclusion

The recommended approach is to leverage Grafana for Prometheus metrics visualization. This provides:

- ✅ Professional, user-friendly UI
- ✅ No additional infrastructure needed
- ✅ Consistent monitoring experience
- ✅ Industry-standard solution
- ✅ Zero cost

The implementation will provide comprehensive system monitoring through 5 new Grafana dashboards, enhanced metric collection via exporters, and automated alerting capabilities.
