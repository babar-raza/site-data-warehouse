# Development Guide

Guide for developers contributing to the GSC Data Warehouse project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Code Standards](#code-standards)
- [Contributing](#contributing)
- [Release Process](#release-process)

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git
- Basic knowledge of:
  - PostgreSQL
  - Google Search Console API
  - Docker
  - REST APIs

### Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/gsc-warehouse
cd gsc-warehouse

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL/gsc-warehouse
```

---

## Development Setup

### Option 1: Local Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov black flake8 mypy

# Run tests
pytest tests/ -v
```

### Option 2: Docker Development

```bash
# Build development images
docker compose build

# Start core services
docker compose up -d warehouse

# Run tests in container
docker compose run --rm api_ingestor pytest /app/tests/
```

### Environment Configuration

```bash
# Copy example environment
cp .env.example .env

# Edit configuration
nano .env

# Add secrets
cp secrets/gsc_sa.json.template secrets/gsc_sa.json
nano secrets/gsc_sa.json
```

---

## Project Structure

```
gsc-warehouse/
├── docs/                           # Documentation
│   ├── ARCHITECTURE.md
│   ├── API_REFERENCE.md
│   ├── RATE_LIMITING.md
│   ├── DEPLOYMENT.md
│   ├── DEVELOPMENT.md
│   └── WINDOWS_QUICKSTART.md
├── compose/                        # Docker configuration
│   ├── dockerfiles/                # Service Dockerfiles
│   ├── init-db/                    # Database initialization
│   └── prometheus/                 # Prometheus config
├── ingestors/
│   └── api/
│       ├── gsc_api_ingestor.py     # Main ingestor
│       ├── rate_limiter.py         # Rate limiter
│       └── api_ingestor.py         # Entry point
├── insights_api/
│   └── insights_api.py             # REST API
├── mcp/
│   └── mcp_server.py               # MCP server
├── scheduler/
│   ├── scheduler.py                # Scheduling
│   └── metrics_exporter.py         # Metrics
├── transform/
│   └── apply_transforms.py         # View creation
├── sql/
│   ├── 01_schema.sql               # Schema
│   └── 03_transforms.sql           # Views
├── tests/                          # Test suite
│   ├── conftest.py                 # Pytest config
│   ├── test_rate_limiter.py
│   ├── test_api_ingestor.py
│   └── test_mcp_server.py
├── docker-compose.yml              # Service orchestration
├── .env.example                    # Environment template
├── requirements.txt                # Dependencies
└── README.md                       # Main documentation
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_rate_limiter.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test
pytest tests/test_rate_limiter.py::TestTokenBucket::test_initialization -v
```

### Writing Tests

```python
# tests/test_new_feature.py
import pytest

def test_my_feature():
    """Test description"""
    # Arrange
    expected = "result"
    
    # Act
    actual = my_function()
    
    # Assert
    assert actual == expected
```

### Test Categories

1. **Unit Tests**: Test individual functions/classes
2. **Integration Tests**: Test service interactions
3. **End-to-End Tests**: Test complete workflows

### Coverage Requirements

- Minimum 80% coverage for new code
- 100% coverage for critical paths:
  - Rate limiting
  - Data ingestion
  - API endpoints

---

## Code Standards

### Python Style

Follow PEP 8 with these tools:

```bash
# Format code
black ingestors/ mcp/ scheduler/ transform/

# Check style
flake8 ingestors/ mcp/ scheduler/ transform/

# Type checking
mypy ingestors/ mcp/ scheduler/ transform/
```

### Code Organization

```python
#!/usr/bin/env python3
"""
Module docstring explaining purpose

Detailed description if needed
"""

import os
import sys
from typing import List, Dict

# Constants
DEFAULT_TIMEOUT = 30

# Classes
class MyClass:
    """Class docstring"""
    
    def __init__(self):
        """Constructor docstring"""
        pass
        
    def method(self, arg: str) -> bool:
        """
        Method docstring
        
        Args:
            arg: Argument description
            
        Returns:
            Return value description
        """
        pass

# Functions
def helper_function(x: int) -> str:
    """Function docstring"""
    pass

# Main
def main():
    """Main entry point"""
    pass

if __name__ == "__main__":
    main()
```

### Docstring Format

Use Google-style docstrings:

```python
def fetch_data(property: str, start_date: date) -> List[Dict]:
    """
    Fetch GSC data for a property
    
    This function queries the Google Search Console API and returns
    search analytics data for the specified property and date range.
    
    Args:
        property: GSC property URL (e.g., "https://example.com/")
        start_date: Start date for data fetch
        
    Returns:
        List of dictionaries containing search analytics data
        
    Raises:
        HttpError: If API request fails
        ValueError: If property URL is invalid
        
    Example:
        >>> data = fetch_data("https://example.com/", date(2025, 1, 1))
        >>> len(data)
        100
    """
    pass
```

### SQL Style

```sql
-- Use descriptive names
CREATE TABLE gsc.fact_gsc_daily (
    property VARCHAR(500) NOT NULL,
    date DATE NOT NULL,
    page VARCHAR(2000),
    -- Use comments
    clicks INTEGER DEFAULT 0,
    
    -- Explicit constraints
    PRIMARY KEY (property, date, page, query, country, device)
);

-- Format queries
SELECT 
    property,
    page,
    SUM(clicks) as total_clicks
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY property, page
ORDER BY total_clicks DESC
LIMIT 10;
```

### Docker Best Practices

```dockerfile
# Use specific versions
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy requirements first (caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Switch to non-root
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "app.py"]
```

---

## Contributing

### Workflow

1. **Create Feature Branch**
```bash
git checkout -b feature/my-feature
```

2. **Make Changes**
```bash
# Write code
# Write tests
# Update documentation
```

3. **Test Changes**
```bash
pytest tests/ -v
black .
flake8 .
```

4. **Commit Changes**
```bash
git add .
git commit -m "feat: add new feature

- Implement feature X
- Add tests for feature X
- Update documentation"
```

5. **Push and Create PR**
```bash
git push origin feature/my-feature
# Create pull request on GitHub
```

### Commit Message Format

Use conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting changes
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

**Examples**:
```
feat(rate-limiter): add burst handling

Implement token bucket algorithm with burst capacity
to handle short spikes in API requests.

Closes #123
```

```
fix(ingestor): handle null query values

Previously null queries caused crashes. Now they are
filtered during ingestion.

Fixes #456
```

### Pull Request Guidelines

**PR Title**: Use conventional commit format

**PR Description**:
```markdown
## Description
Brief description of changes

## Changes
- Change 1
- Change 2

## Testing
- [ ] Tests added/updated
- [ ] Manual testing completed
- [ ] Documentation updated

## Screenshots (if UI changes)

## Related Issues
Closes #123
```

**Review Process**:
1. CI checks must pass
2. At least one approval required
3. No merge conflicts
4. Documentation updated

---

## Development Patterns

### Adding a New Service

1. **Create Dockerfile**
```dockerfile
# compose/dockerfiles/Dockerfile.new_service
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY new_service/ .
CMD ["python", "server.py"]
```

2. **Update docker-compose.yml**
```yaml
services:
  new_service:
    build:
      dockerfile: ./compose/dockerfiles/Dockerfile.new_service
    environment:
      - SERVICE_CONFIG=value
    networks:
      - gsc_network
```

3. **Add Tests**
```python
# tests/test_new_service.py
def test_new_service():
    pass
```

4. **Update Documentation**
- README.md
- docs/ARCHITECTURE.md
- docs/API_REFERENCE.md

### Adding a New MCP Tool

1. **Define Tool**
```python
# mcp/mcp_server.py
@app.post("/tools/new_tool")
async def new_tool(args: Dict):
    """New tool description"""
    # Implementation
    return result
```

2. **Add Tests**
```python
# tests/test_mcp_tools.py
def test_new_tool():
    response = client.post("/tools/new_tool", json={...})
    assert response.status_code == 200
```

3. **Document**
```markdown
# docs/API_REFERENCE.md
#### new_tool
Description of tool...
```

### Adding a Database View

1. **Create SQL**
```sql
-- sql/03_transforms.sql
CREATE OR REPLACE VIEW gsc.vw_new_view AS
SELECT ...
FROM gsc.fact_gsc_daily
WHERE ...;
```

2. **Update Transformer**
```python
# transform/apply_transforms.py
views_to_create = [
    'vw_existing_view',
    'vw_new_view'
]
```

3. **Add Tests**
```python
def test_new_view_creation():
    # Test view exists and returns data
    pass
```

---

## Debugging

### Local Debugging

```python
# Add to code
import pdb; pdb.set_trace()

# Or use logging
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug message")
```

### Docker Debugging

```bash
# View logs
docker compose logs -f service_name

# Execute commands in container
docker compose exec service_name bash

# Check service status
docker compose ps

# Inspect container
docker inspect container_name
```

### Database Debugging

```bash
# Connect to database
docker compose exec warehouse psql -U gsc_user -d gsc_db

# View tables
\dt gsc.*

# View views
\dv gsc.*

# Query data
SELECT * FROM gsc.fact_gsc_daily LIMIT 10;

# Check indexes
\di gsc.*
```

---

## Performance Optimization

### Database Optimization

```sql
-- Add indexes
CREATE INDEX idx_custom ON gsc.fact_gsc_daily (column);

-- Analyze tables
ANALYZE gsc.fact_gsc_daily;

-- Vacuum
VACUUM ANALYZE gsc.fact_gsc_daily;
```

### Python Optimization

```python
# Use generators for large datasets
def process_large_dataset():
    for item in large_list:
        yield process(item)

# Batch database operations
execute_values(cursor, query, values, page_size=1000)

# Cache expensive operations
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_function(arg):
    pass
```

### Docker Optimization

```dockerfile
# Multi-stage builds
FROM python:3.11-slim AS builder
# Build steps

FROM python:3.11-slim
COPY --from=builder /app /app
```

---

## Release Process

### Version Numbering

Use Semantic Versioning: `MAJOR.MINOR.PATCH`

- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Checklist

1. **Update Version**
```python
# version.py
__version__ = "2.1.0"
```

2. **Update Changelog**
```markdown
# CHANGELOG.md
## [2.1.0] - 2025-11-09
### Added
- Feature X
### Fixed
- Bug Y
```

3. **Run Tests**
```bash
pytest tests/ -v
```

4. **Build and Test Docker**
```bash
docker compose build
docker compose up -d
# Manual testing
```

5. **Create Release**
```bash
git tag -a v2.1.0 -m "Release version 2.1.0"
git push origin v2.1.0
```

6. **Update Documentation**
- README.md version
- Documentation dates

---

## Resources

### Documentation
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Google Search Console API](https://developers.google.com/webmaster-tools/search-console-api-original)
- [Docker Compose](https://docs.docker.com/compose/)
- [FastAPI](https://fastapi.tiangolo.com/)

### Tools
- [pytest](https://docs.pytest.org/)
- [black](https://black.readthedocs.io/)
- [flake8](https://flake8.pycqa.org/)
- [mypy](https://mypy.readthedocs.io/)

### Community
- GitHub Issues
- Discussions
- Pull Requests

---

*Last Updated: November 2025*
