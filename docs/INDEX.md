# Documentation Index

**Complete documentation for the GSC Data Warehouse / Hybrid Insight Engine**

---

## Getting Started
- **[Main README](../README.md)** - Project overview and quick start
- **[QUICKSTART](QUICKSTART.md)** - 15-minute deployment guide
- **[Deployment Guide](../deployment/README.md)** - Comprehensive deployment instructions

## Account & API Setup Guides

### Google Cloud Platform
- **[GCP Setup Guide](../deployment/guides/GCP_SETUP_GUIDE.md)** - Complete GCP project, service account, and API setup
- **[GSC Integration](../deployment/guides/GSC_INTEGRATION.md)** - Google Search Console API integration
- **[GA4 Integration](../deployment/guides/GA4_INTEGRATION.md)** - Google Analytics 4 API integration

### Additional API Integrations
- **[Google Custom Search (CSE) Integration](QUICK_REFERENCE_CSE_INTEGRATION.md)** - Google Custom Search API for SERP analysis
- **[PageSpeed Setup](PAGESPEED_SETUP.md)** - PageSpeed Insights API integration
- **[SERP Tracking Guide](SERP_TRACKING_GUIDE.md)** - Search engine results page tracking
- **[GSC SERP Tracking](GSC_SERP_TRACKING.md)** - GSC-based SERP tracking
- **[MCP Integration](guides/MCP_INTEGRATION.md)** - Claude Desktop MCP server integration

## Core Documentation

### Architecture & Design
- **[ARCHITECTURE](ARCHITECTURE.md)** - System design and components
- **[ARCHITECTURE_PATTERNS](ARCHITECTURE_PATTERNS.md)** - Design patterns used
- **[guides/UNIFIED_VIEW_GUIDE](guides/UNIFIED_VIEW_GUIDE.md)** - Deep dive into hybrid data layer
- **[api/API_REFERENCE](api/API_REFERENCE.md)** - API endpoints and schemas

### Development
- **[guides/DEVELOPMENT](guides/DEVELOPMENT.md)** - Development setup
- **[guides/DETECTOR_GUIDE](guides/DETECTOR_GUIDE.md)** - Writing custom detectors
- **[QUICK_REFERENCE](QUICK_REFERENCE.md)** - Quick command reference

### Insight Engine & Multi-Agent System
- **[analysis/INSIGHT_ENGINE_GUIDE](analysis/INSIGHT_ENGINE_GUIDE.md)** - Complete Insight Engine documentation
- **[analysis/MULTI_AGENT_SYSTEM](analysis/MULTI_AGENT_SYSTEM.md)** - Multi-Agent System architecture and usage
- **[analysis/SYSTEM_OVERVIEW](analysis/SYSTEM_OVERVIEW.md)** - System overview and data flows
- **[analysis/TECHNICAL_ARCHITECTURE](analysis/TECHNICAL_ARCHITECTURE.md)** - Technical architecture details
- **[analysis/DASHBOARD_GUIDE](analysis/DASHBOARD_GUIDE.md)** - Grafana dashboards guide

### Feature Guides
- **[guides/HUGO_CONTENT_OPTIMIZER](guides/HUGO_CONTENT_OPTIMIZER.md)** - Automated Hugo content optimization
- **[guides/URL_VARIATIONS_GUIDE](guides/URL_VARIATIONS_GUIDE.md)** - URL path tracking and variations
- **[guides/URL_CONSOLIDATION_GUIDE](guides/URL_CONSOLIDATION_GUIDE.md)** - URL consolidation logic
- **[guides/ACTIONS_COMMAND_CENTER](guides/ACTIONS_COMMAND_CENTER.md)** - Actions system documentation
- **[guides/ACTIONS_DASHBOARD_QUICK_START](guides/ACTIONS_DASHBOARD_QUICK_START.md)** - Actions dashboard setup
- **[guides/PROMETHEUS_DASHBOARDS_GUIDE](guides/PROMETHEUS_DASHBOARDS_GUIDE.md)** - Prometheus dashboards setup
- **[guides/QUICK_START_PHASE1](guides/QUICK_START_PHASE1.md)** - Phase 1 quick start guide

### Testing
- **[testing/TESTING](testing/TESTING.md)** - Comprehensive testing documentation
- **[testing/INTEGRATION_README](testing/INTEGRATION_README.md)** - Integration testing guide
- **[testing/TEST_SUMMARY_LIVE_OLLAMA](testing/TEST_SUMMARY_LIVE_OLLAMA.md)** - LLM integration testing

### Operations
- **[DEPLOYMENT](DEPLOYMENT.md)** - Deployment instructions overview
- **[TROUBLESHOOTING](TROUBLESHOOTING.md)** - Common issues and solutions

## Deployment Resources

The `../deployment/` folder contains:
- **[deployment/README.md](../deployment/README.md)** - Deployment overview
- **[deployment/guides/SETUP_GUIDE.md](../deployment/guides/SETUP_GUIDE.md)** - Initial setup instructions
- **[deployment/guides/GCP_SETUP_GUIDE.md](../deployment/guides/GCP_SETUP_GUIDE.md)** - Google Cloud Platform setup
- **[deployment/guides/GSC_INTEGRATION.md](../deployment/guides/GSC_INTEGRATION.md)** - GSC API integration
- **[deployment/guides/GA4_INTEGRATION.md](../deployment/guides/GA4_INTEGRATION.md)** - GA4 API integration
- **[deployment/guides/PRODUCTION_GUIDE.md](../deployment/guides/PRODUCTION_GUIDE.md)** - Production best practices
- **[deployment/guides/MONITORING_GUIDE.md](../deployment/guides/MONITORING_GUIDE.md)** - Monitoring and observability
- **[deployment/DEPLOYMENT_CHECKLIST.md](deployment/DEPLOYMENT_CHECKLIST.md)** - Deployment checklist
- **[deployment/DOCKER_RESOURCE_LIMITS.md](deployment/DOCKER_RESOURCE_LIMITS.md)** - Docker resource configuration
- **[deployment/DOCKER_IMPLEMENTATION_GUIDE.md](deployment/DOCKER_IMPLEMENTATION_GUIDE.md)** - Docker implementation details
- **[deployment/DEPLOYMENT_WITH_LIMITS.md](deployment/DEPLOYMENT_WITH_LIMITS.md)** - Deployment with resource limits
- Scripts for Windows and Linux deployments

## Implementation Documentation

- **[implementation/PHASE1_SETUP_GUIDE.md](implementation/PHASE1_SETUP_GUIDE.md)** - Phase 1 implementation guide
- **[implementation/PHASE2_SETUP_GUIDE.md](implementation/PHASE2_SETUP_GUIDE.md)** - Phase 2 implementation guide
- **[implementation/TASKCARD-024-URL-VARIATIONS.md](implementation/TASKCARD-024-URL-VARIATIONS.md)** - URL variations implementation
- **[implementation/TASKCARD-028_IMPLEMENTATION.md](implementation/TASKCARD-028_IMPLEMENTATION.md)** - URL consolidation implementation
- **[implementation/TASKCARD-040-CSE-INTEGRATION.md](implementation/TASKCARD-040-CSE-INTEGRATION.md)** - Google CSE integration

## Documentation Structure
```
docs/
├── INDEX.md                     # This file - documentation index
├── QUICKSTART.md                # Fast deployment guide
├── ARCHITECTURE.md              # System architecture
├── ARCHITECTURE_PATTERNS.md     # Design patterns
├── DEPLOYMENT.md                # Deployment overview
├── TROUBLESHOOTING.md           # Issue resolution
├── QUICK_REFERENCE.md           # Quick command reference
├── PAGESPEED_SETUP.md           # PageSpeed API setup
├── SERP_TRACKING_GUIDE.md       # SERP tracking guide
├── GSC_SERP_TRACKING.md         # GSC SERP tracking
├── QUICK_REFERENCE_CSE_INTEGRATION.md # Google Custom Search API
│
├── api/                         # API Documentation
│   └── API_REFERENCE.md         # API endpoints and schemas
│
├── guides/                      # Development & Feature Guides
│   ├── UNIFIED_VIEW_GUIDE.md    # Hybrid data layer guide
│   ├── DETECTOR_GUIDE.md        # Custom detector development
│   ├── DEVELOPMENT.md           # Development setup
│   ├── MCP_INTEGRATION.md       # MCP server integration
│   ├── HUGO_CONTENT_OPTIMIZER.md # Hugo content optimization
│   ├── URL_VARIATIONS_GUIDE.md  # URL variations tracking
│   ├── URL_CONSOLIDATION_GUIDE.md # URL consolidation logic
│   ├── ACTIONS_COMMAND_CENTER.md # Actions system
│   ├── ACTIONS_DASHBOARD_QUICK_START.md # Actions dashboard
│   ├── PROMETHEUS_DASHBOARDS_GUIDE.md # Prometheus dashboards
│   └── QUICK_START_PHASE1.md    # Phase 1 quick start
│
├── testing/                     # Testing Documentation
│   ├── TESTING.md               # Comprehensive testing guide
│   ├── INTEGRATION_README.md    # Integration testing
│   └── TEST_SUMMARY_LIVE_OLLAMA.md # LLM testing
│
├── analysis/                    # System Analysis & Guides
│   ├── SYSTEM_OVERVIEW.md       # System overview
│   ├── TECHNICAL_ARCHITECTURE.md # Technical architecture
│   ├── INSIGHT_ENGINE_GUIDE.md  # Insight Engine guide
│   ├── MULTI_AGENT_SYSTEM.md    # Multi-Agent System guide
│   └── DASHBOARD_GUIDE.md       # Dashboard guide
│
├── deployment/                  # Deployment Documentation
│   ├── DEPLOYMENT_CHECKLIST.md  # Deployment checklist
│   ├── DOCKER_RESOURCE_LIMITS.md # Docker resources
│   ├── DOCKER_IMPLEMENTATION_GUIDE.md # Docker implementation
│   └── DEPLOYMENT_WITH_LIMITS.md # Deployment with limits
│
└── implementation/              # Feature Implementation Docs
    ├── PHASE1_SETUP_GUIDE.md    # Phase 1 setup
    ├── PHASE2_SETUP_GUIDE.md    # Phase 2 setup
    └── TASKCARD-*.md            # Implementation details
```

---

## Quick Links

### For New Users
1. Start with [Main README](../README.md) for project overview
2. Follow [QUICKSTART](QUICKSTART.md) for 15-minute setup
3. Setup Google Cloud with [GCP Setup Guide](../deployment/guides/GCP_SETUP_GUIDE.md)
4. Check [TROUBLESHOOTING](TROUBLESHOOTING.md) if issues arise

### For Developers
1. Read [ARCHITECTURE](ARCHITECTURE.md) to understand the system
2. Follow [guides/DEVELOPMENT](guides/DEVELOPMENT.md) for dev setup
3. Use [guides/DETECTOR_GUIDE](guides/DETECTOR_GUIDE.md) to add detectors
4. Read [analysis/INSIGHT_ENGINE_GUIDE](analysis/INSIGHT_ENGINE_GUIDE.md) for Insight Engine details
5. Read [analysis/MULTI_AGENT_SYSTEM](analysis/MULTI_AGENT_SYSTEM.md) for agent architecture
6. Review [testing/TESTING](testing/TESTING.md) for testing practices

### For Operators
1. Use [deployment/README.md](../deployment/README.md) for deployment
2. Setup APIs with [GCP Setup Guide](../deployment/guides/GCP_SETUP_GUIDE.md)
3. Follow [deployment/guides/PRODUCTION_GUIDE.md](../deployment/guides/PRODUCTION_GUIDE.md) for production
4. Setup monitoring with [deployment/guides/MONITORING_GUIDE.md](../deployment/guides/MONITORING_GUIDE.md)
5. Configure dashboards with [guides/PROMETHEUS_DASHBOARDS_GUIDE](guides/PROMETHEUS_DASHBOARDS_GUIDE.md)
6. Refer to [TROUBLESHOOTING](TROUBLESHOOTING.md) for common issues

---

**Last Updated**: 2025-11-27
