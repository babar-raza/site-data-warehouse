# Deployment Scripts

This package contains all deployment scripts and guides for the GSC Data Warehouse (Hybrid Plan).

## Quick Start

### Linux
```bash
cd linux
./deploy.sh
```

### Windows
```cmd
cd windows
deploy.bat
```

## Package Contents

```
deployment/
├── linux/
│   ├── deploy.sh       # Main deployment script
│   ├── stop.sh         # Stop services
│   ├── logs.sh         # View logs
│   └── backup.sh       # Backup database
│
├── windows/
│   ├── deploy.bat      # Main deployment script
│   ├── stop.bat        # Stop services
│   ├── logs.bat        # View logs
│   └── backup.bat      # Backup database
│
├── docker/
│   └── docker-compose.yml  # Docker orchestration
│
└── guides/
    ├── SETUP_GUIDE.md      # Initial setup
    ├── GCP_SETUP_GUIDE.md  # Google Cloud Platform setup
    ├── GSC_INTEGRATION.md  # Google Search Console integration
    ├── GA4_INTEGRATION.md  # Google Analytics 4 integration
    ├── PRODUCTION_GUIDE.md # Production deployment
    └── MONITORING_GUIDE.md # Monitoring setup
```

## Prerequisites

- Docker 20.10+
- Docker Compose 1.29+
- PostgreSQL Client (psql)
- Python 3.9+
- Git

## First-Time Setup

### Step 1: Google Cloud Platform Setup
**Important:** Complete GCP setup before deploying the application.

Follow [GCP_SETUP_GUIDE.md](guides/GCP_SETUP_GUIDE.md) to:
- Create Google Cloud project
- Enable APIs (Search Console API, Analytics Data API)
- Create service account and download credentials
- Add service account to GSC and GA4 properties

### Step 2: Clone Repository
```bash
git clone <repository-url>
cd gsc-data-warehouse
```

### Step 3: Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings:
# - GSC_PROPERTIES (your Search Console properties)
# - GA4_PROPERTY_ID (your Analytics property ID)
# - Database passwords
# - Other configuration
```

### Step 4: Setup Credentials
```bash
# Create secrets directory (if not exists)
mkdir -p secrets

# Copy your service account JSON from GCP
# Rename to gsc_sa.json
cp ~/Downloads/your-project-*.json secrets/gsc_sa.json

# Secure the file
chmod 600 secrets/gsc_sa.json  # Linux/Mac
```

### Step 5: Run Deployment
- **Linux:** `./deployment/linux/deploy.sh`
- **Windows:** `deployment\windows\deploy.bat`

### Step 6: Verify Setup
See [SETUP_GUIDE.md](guides/SETUP_GUIDE.md) for verification steps.

## Available Scripts

### Linux

**deploy.sh** - Full deployment
- Starts database
- Runs migrations
- Validates schema
- Starts all services
- Performs health checks

**stop.sh** - Stop all services
```bash
./stop.sh
```

**logs.sh** - View service logs
```bash
./logs.sh all              # All services
./logs.sh insights_engine  # Specific service
```

**backup.sh** - Backup database
```bash
./backup.sh
```

### Windows

Same functionality, Windows batch file versions.

## Deployment Guides

### Getting Started
- **[SETUP_GUIDE.md](guides/SETUP_GUIDE.md)** - Complete setup instructions from scratch
  - Installation steps
  - Initial data load
  - Verification procedures

### Google Cloud Platform Setup
- **[GCP_SETUP_GUIDE.md](guides/GCP_SETUP_GUIDE.md)** - **Start here for Google Cloud setup**
  - Creating Google Cloud projects
  - Enabling required APIs (Search Console, Analytics Data)
  - Creating service accounts with IAM roles
  - Downloading service account credentials
  - Security best practices
  - Comprehensive troubleshooting

- **[GSC_INTEGRATION.md](guides/GSC_INTEGRATION.md)** - Google Search Console integration
  - Adding service account to GSC properties
  - Property URL formats and configuration
  - Testing GSC API access
  - Data collection verification
  - Troubleshooting GSC-specific issues

- **[GA4_INTEGRATION.md](guides/GA4_INTEGRATION.md)** - Google Analytics 4 integration
  - Adding service account to GA4 properties
  - Finding and configuring Property IDs
  - Understanding GA4 metrics and dimensions
  - Testing GA4 API access
  - Troubleshooting GA4-specific issues

### Production & Operations
- **[PRODUCTION_GUIDE.md](guides/PRODUCTION_GUIDE.md)** - Production deployment best practices
  - Security hardening
  - Performance tuning
  - Backup strategy
  - Monitoring setup
  - Scaling considerations

- **[MONITORING_GUIDE.md](guides/MONITORING_GUIDE.md)** - Monitoring and observability
  - Grafana dashboards
  - Key metrics
  - Alerting rules
  - Health checks
  - Log management

---

## Troubleshooting

See [../docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) for:
- Database connection issues
- Migration failures
- Service startup problems
- Performance optimization

---

## Support

For issues or questions:
1. Check [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)
2. Review service logs: `./logs.sh <service>` (Linux) or `logs.bat <service>` (Windows)
3. Check database health: `psql $WAREHOUSE_DSN -c "SELECT 1;"`
4. Validate schema: `psql $WAREHOUSE_DSN -c "SELECT * FROM gsc.validate_unified_view_time_series();"`

---

## Related Documentation

- **[Main README](../README.md)** - Project overview
- **[Quick Start Guide](../docs/QUICKSTART.md)** - Fast deployment
- **[Architecture Guide](../docs/ARCHITECTURE.md)** - System design
- **[Secrets Setup](../secrets/README.md)** - Credential management

---

**Last Updated**: 2025-11-21
