# System Architecture

## Overview

The GSC Data Warehouse is a microservices-based data platform designed for reliability, scalability, and maintainability. All services run in Docker containers with health checks and automatic restarts.

## Architecture Principles

1. **Separation of Concerns**: Each service has a single, well-defined responsibility
2. **Idempotency**: All operations can be safely retried
3. **Observability**: Comprehensive logging, metrics, and health checks
4. **Resilience**: Automatic retries, backoff, and graceful degradation
5. **Security**: Docker secrets, isolated networks, no exposed credentials

## System Diagram

```
┌─────────────────────────────────────────────────────┐
│                 External Systems                     │
├─────────────────────────────────────────────────────┤
│  Google Search Console API                          │
│  └─ Properties, Pages, Queries, Metrics             │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │      API Ingestor Service    │
    │  ┌────────────────────────┐  │
    │  │  Enterprise Rate       │  │
    │  │  Limiter               │  │
    │  │  - Token Bucket        │  │
    │  │  - Exp. Backoff        │  │
    │  │  - Per-Property Track  │  │
    │  └────────────────────────┘  │
    │  ┌────────────────────────┐  │
    │  │  Data Transformer      │  │
    │  │  - API → Warehouse     │  │
    │  │  - Validation          │  │
    │  └────────────────────────┘  │
    └────────────┬─────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │   PostgreSQL  │
         │   Warehouse   │
         ├───────────────┤
         │ gsc schema    │
         │ - Properties  │
         │ - Facts       │
         │ - Watermarks  │
         │ - Audit Log   │
         └───────┬───────┘
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
┌─────────────┐       ┌──────────────┐
│ Transformer │       │  Analytical  │
│  Service    │──────►│    Views     │
├─────────────┤       ├──────────────┤
│ SQL DDL     │       │ Page Health  │
│ View Mgmt   │       │ Query Trends │
│             │       │ Directories  │
│             │       │ Brand Split  │
└─────────────┘       └──────┬───────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
      ┌───────────┐  ┌──────────┐  ┌──────────┐
      │    MCP    │  │ Insights │  │  Direct  │
      │  Server   │  │   API    │  │   SQL    │
      ├───────────┤  ├──────────┤  ├──────────┤
      │ Port 8000 │  │ Port 8001│  │ Port 5432│
      │ Tools API │  │ REST API │  │ psql     │
      └─────┬─────┘  └────┬─────┘  └────┬─────┘
            │             │              │
            ▼             ▼              ▼
    ┌─────────────────────────────────────────┐
    │          Client Applications            │
    ├─────────────────────────────────────────┤
    │ • Claude Desktop                        │
    │ • ChatGPT Plugins                       │
    │ • Custom Dashboards                     │
    │ • SQL Clients                           │
    │ • BI Tools                              │
    └─────────────────────────────────────────┘

         ┌──────────────────┐
         │   Scheduler      │
         │   Service        │
         ├──────────────────┤
         │ Daily:           │
         │  02:00 UTC       │
         │  - API Ingest    │
         │  - Transforms    │
         │                  │
         │ Weekly:          │
         │  Sun 03:00 UTC   │
         │  - Reconcile     │
         │  - Refresh       │
         └──────────────────┘

         ┌──────────────────┐
         │  Observability   │
         ├──────────────────┤
         │ Metrics Exporter │
         │ Port 9090        │
         │       ▼          │
         │  Prometheus      │
         │  Port 9091       │
         │       ▼          │
         │  (Future)        │
         │  Grafana         │
         │  Alertmanager    │
         └──────────────────┘
```

## Services

### 1. Warehouse (PostgreSQL)

**Purpose**: Central data store for all GSC data

**Technology**: PostgreSQL 15 Alpine

**Responsibilities**:
- Store raw GSC data
- Maintain watermarks and audit logs
- Host analytical views
- Provide ACID guarantees

**Key Features**:
- UPSERT logic for idempotency
- Composite primary keys
- 7 indexes on fact table
- Automatic timestamp management
- Health checks via pg_isready

**Configuration**:
```yaml
environment:
  POSTGRES_DB: gsc_db
  POSTGRES_USER: gsc_user
  POSTGRES_PASSWORD_FILE: /run/secrets/db_password
ports:
  - "5432:5432"
volumes:
  - warehouse_data:/var/lib/postgresql/data
```

### 2. API Ingestor

**Purpose**: Fetch data from Google Search Console API

**Technology**: Python 3.11

**Responsibilities**:
- Connect to GSC API
- Apply enterprise rate limiting
- Transform API responses
- Upsert to warehouse
- Track watermarks

**Key Features**:
- Token bucket rate limiting
- Exponential backoff
- Per-property tracking
- Automatic retry logic
- Comprehensive error handling

**Configuration**:
```yaml
environment:
  REQUESTS_PER_MINUTE: 30
  REQUESTS_PER_DAY: 2000
  BURST_SIZE: 5
  API_COOLDOWN_SEC: 2
  GSC_API_MAX_RETRIES: 5
```

### 3. Transformer

**Purpose**: Create and refresh analytical views

**Technology**: Python 3.11

**Responsibilities**:
- Execute SQL DDL
- Create views
- Refresh materialized views (future)
- Validate view integrity

**Configuration**:
```yaml
volumes:
  - ./transform:/app
  - ./sql:/sql:ro
```

### 4. MCP Server

**Purpose**: Provide AI agent integration via Model Context Protocol

**Technology**: Python 3.11 + FastAPI

**Responsibilities**:
- Expose MCP tools
- Query warehouse
- Format responses for LLMs
- Handle tool invocations

**Endpoints**:
- `GET /health` - Health check
- `POST /call-tool` - Tool invocation
- `GET /tools` - List available tools

**Configuration**:
```yaml
ports:
  - "8000:8000"
environment:
  MCP_VERSION: "2025-01-18"
```

### 5. Scheduler

**Purpose**: Orchestrate automated pipeline execution

**Technology**: Python 3.11 + APScheduler

**Responsibilities**:
- Run daily API ingestion
- Execute weekly maintenance
- Trigger transforms
- Log execution metrics

**Schedule**:
- **Daily** (02:00 UTC): API ingestion, transforms
- **Weekly** (Sun 03:00 UTC): Reconciliation, refresh

**Configuration**:
```yaml
environment:
  TZ: UTC
  ONESHOT: false  # Set true for testing
```

### 6. Insights API

**Purpose**: REST API for dashboards and applications

**Technology**: Python 3.11 + FastAPI

**Endpoints**:
- `GET /api/health` - Health check
- `GET /api/page-health` - Page performance
- `GET /api/query-trends` - Query trends
- `GET /api/directory-trends` - Directory stats
- `GET /api/brand-nonbrand` - Brand analysis

**Configuration**:
```yaml
ports:
  - "8001:8001"
environment:
  API_VERSION: "1.0.0"
```

### 7. Metrics Exporter

**Purpose**: Export Prometheus metrics

**Technology**: Python 3.11 + Flask

**Metrics**:
- Rate limiter statistics
- Database health
- Task execution
- Data freshness

**Configuration**:
```yaml
ports:
  - "9090:9090"
environment:
  METRICS_PORT: 9090
```

### 8. Prometheus

**Purpose**: Metrics collection and storage

**Technology**: Prometheus

**Configuration**:
```yaml
ports:
  - "9091:9090"
volumes:
  - prometheus_data:/prometheus
```

## Data Flow

### Ingestion Flow

```
1. Scheduler triggers → API Ingestor
2. API Ingestor:
   a. Checks watermarks
   b. Acquires rate limit permission
   c. Calls GSC API
   d. Transforms response
   e. Upserts to warehouse
   f. Updates watermarks
3. Transformer:
   a. Refreshes analytical views
   b. Validates integrity
4. Services:
   a. MCP/API serve fresh data
```

### Query Flow

```
1. Client → MCP Server/Insights API
2. Service:
   a. Validates request
   b. Queries warehouse views
   c. Formats response
3. Client ← Response
```

## Networking

### Network Topology

```
┌─────────────────────────────────────┐
│         gsc_network (bridge)        │
├─────────────────────────────────────┤
│                                     │
│  ┌──────────┐    ┌──────────┐     │
│  │warehouse │◄───│api_ingest│     │
│  └────┬─────┘    └──────────┘     │
│       │                             │
│       ├──────────┬──────────┐      │
│       ▼          ▼          ▼      │
│  ┌────────┐ ┌────────┐ ┌────────┐ │
│  │  mcp   │ │insights│ │ sched  │ │
│  └────────┘ └────────┘ └────────┘ │
│                                     │
└─────────────────────────────────────┘
       │                  │
       ▼                  ▼
    Port 8000         Port 8001
    (External)        (External)
```

### Security

1. **Isolated Network**: All services on private bridge network
2. **Secrets Management**: Credentials via Docker secrets
3. **Minimal Exposure**: Only necessary ports exposed
4. **No Root**: Services run as non-root users
5. **Read-Only Mounts**: Configuration as read-only

## Scalability

### Current Capacity

- **Data Volume**: 1M+ rows
- **Properties**: Unlimited
- **Throughput**: 30 req/min sustained
- **Daily Quota**: 2000 requests

### Scaling Strategies

#### Vertical Scaling
```yaml
# Increase resources
services:
  warehouse:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

#### Horizontal Scaling
```yaml
# Multiple ingestors
services:
  api_ingestor_1:
    environment:
      PROPERTY_GROUP: "group1"
  api_ingestor_2:
    environment:
      PROPERTY_GROUP: "group2"
```

#### Database Scaling
- Read replicas for queries
- Partitioning by date
- Archiving old data

## Reliability

### Health Checks

All services implement health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### Restart Policies

```yaml
restart: unless-stopped  # Core services
restart: "no"           # One-shot jobs
```

### Data Integrity

- UPSERT prevents duplicates
- Watermarks track progress
- Audit logs record changes
- Idempotent operations

## Monitoring

### Logs

```bash
# All logs centralized
docker compose logs -f

# Service-specific
docker compose logs -f api_ingestor

# Filter by level
docker compose logs | grep ERROR
```

### Metrics

```bash
# Prometheus metrics
curl http://localhost:9091/metrics

# Custom metrics
curl http://localhost:9090/metrics
```

### Alerts (Future)

```yaml
# alertmanager.yml
groups:
  - name: gsc_alerts
    rules:
      - alert: HighThrottleRate
        expr: gsc_api_throttle_rate > 0.1
        annotations:
          summary: "High API throttle rate"
```

## Deployment Patterns

### Development
```bash
docker compose up -d warehouse mcp
# Manual testing
```

### Staging
```bash
docker compose up -d \
  --profile ingestion \
  --profile api
# Automated testing
```

### Production
```bash
docker compose up -d \
  --profile ingestion \
  --profile scheduler \
  --profile api \
  --profile observability
# Full monitoring
```

## Security Considerations

1. **Secrets**: Never commit secrets to repository
2. **Network**: Use isolated bridge network
3. **Passwords**: Strong passwords in production
4. **TLS**: Enable TLS for exposed services
5. **Updates**: Regular security updates
6. **Logs**: Sanitize sensitive data in logs

## Performance Optimization

### Database
- Indexes on frequently queried columns
- Vacuum and analyze regularly
- Connection pooling
- Query optimization

### Rate Limiting
- Tune based on actual quota usage
- Monitor throttle rates
- Adjust burst size for workload

### Caching
- Cache analytical views
- Materialize views for heavy queries
- Cache MCP responses

## Disaster Recovery

### Backups

```bash
# Backup database
docker compose exec warehouse pg_dump \
  -U gsc_user gsc_db > backup.sql

# Backup volumes
docker run --rm -v gsc_warehouse_data:/data \
  -v $(pwd):/backup alpine \
  tar czf /backup/warehouse_data.tar.gz /data
```

### Restore

```bash
# Restore database
docker compose exec -T warehouse psql \
  -U gsc_user gsc_db < backup.sql

# Restore volumes
docker run --rm -v gsc_warehouse_data:/data \
  -v $(pwd):/backup alpine \
  tar xzf /backup/warehouse_data.tar.gz -C /data
```

---

*Last Updated: November 2025*
