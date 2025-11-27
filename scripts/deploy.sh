#!/bin/bash
# ============================================================================
# One-Command Deployment Script
# ============================================================================
# Complete deployment of SEO Intelligence Platform

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SEO Intelligence Platform${NC}"
echo -e "${GREEN}Complete Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
echo "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo -e "${RED}✗ Docker not found${NC}"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}✗ Docker Compose not found${NC}"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}✗ Python 3 not found${NC}"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo -e "${RED}✗ PostgreSQL client not found${NC}"; exit 1; }
echo -e "${GREEN}✓ All prerequisites met${NC}\n"

# 1. Initialize database
echo -e "${YELLOW}Step 1: Initializing database...${NC}"
bash scripts/setup/init_database.sh
echo -e "${GREEN}✓ Database initialized${NC}\n"

# 2. Install Python dependencies
echo -e "${YELLOW}Step 2: Installing Python dependencies...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓ Dependencies installed${NC}\n"

# 3. Create logs directory
echo -e "${YELLOW}Step 3: Creating directories...${NC}"
mkdir -p logs backups
echo -e "${GREEN}✓ Directories created${NC}\n"

# 4. Seed initial data
echo -e "${YELLOW}Step 4: Seeding initial data...${NC}"
python scripts/setup/seed_data.py
echo -e "${GREEN}✓ Data seeded${NC}\n"

# 5. Start all services
echo -e "${YELLOW}Step 5: Starting services...${NC}"
bash scripts/setup/start_services.sh
echo -e "${GREEN}✓ Services started${NC}\n"

# 6. Run health check
echo -e "${YELLOW}Step 6: Running health check...${NC}"
python scripts/setup/health_check.py
echo -e "${GREEN}✓ Health check complete${NC}\n"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Access Points:${NC}"
echo "  Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo "1. Configure your API credentials in .env"
echo "2. Add your SERP tracking queries"
echo "3. Trigger first data collection:"
echo "   celery -A services.tasks call collect_gsc_data"
echo ""
