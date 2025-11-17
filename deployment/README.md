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

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd gsc-data-warehouse
   ```

2. **Create .env file**
   ```bash
   cp .env.template .env
   # Edit .env with your settings
   ```

3. **Setup secrets**
   ```bash
   cp secrets/gsc_sa.json.template secrets/gsc_sa.json
   # Add your GSC credentials
   ```

4. **Run deployment**
   - Linux: `./deployment/linux/deploy.sh`
   - Windows: `deployment\windows\deploy.bat`

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

## Guides

### [SETUP_GUIDE.md](guides/SETUP_GUIDE.md)
Complete setup instructions from scratch

### [PRODUCTION_GUIDE.md](guides/PRODUCTION_GUIDE.md)
Production deployment best practices:
- Security hardening
- Performance tuning
- Backup strategy
- Monitoring setup
- Scaling considerations

### [MONITORING_GUIDE.md](guides/MONITORING_GUIDE.md)
Monitoring and observability:
- Grafana dashboards
- Key metrics
- Alerting rules
- Health checks
- Log management

## Troubleshooting

See [../../docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md) for:
- Database connection issues
- Migration failures
- Service startup problems
- Performance optimization

## Support

For issues or questions:
1. Check [TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)
2. Review service logs: `./logs.sh <service>`
3. Check database health: `psql $WAREHOUSE_DSN -c "SELECT 1;"`
4. Validate schema: `psql $WAREHOUSE_DSN -c "SELECT * FROM gsc.validate_unified_view_time_series();"`
