#!/bin/bash
# ============================================
# Rotate Secrets (PRODUCTION ONLY)
# ============================================
# Zero-downtime secret rotation procedure
# Only needed for production deployments
#
# Usage:
#   bash security/rotate_secrets.sh [secret_name]
#   bash security/rotate_secrets.sh --all

set -e

SECRETS_DIR="./secrets"
BACKUP_DIR="./secrets/backup"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "GSC Warehouse - Secret Rotation"
echo "============================================"
echo ""
echo -e "${YELLOW}NOTE:${NC} This is for production deployments only"
echo "      Development setups can use .env file"
echo ""

generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

backup_secret() {
    local secret_name=$1
    local timestamp=$(date +%Y%m%d_%H%M%S)
    
    mkdir -p "${BACKUP_DIR}"
    
    if [ -f "${SECRETS_DIR}/${secret_name}" ]; then
        cp "${SECRETS_DIR}/${secret_name}" "${BACKUP_DIR}/${secret_name}.${timestamp}"
        echo -e "${GREEN}✓${NC} Backed up: ${secret_name}"
    fi
}

rotate_db_password() {
    echo ""
    echo "Rotating database password..."
    echo ""
    
    backup_secret "db_password"
    
    NEW_PASSWORD=$(generate_password)
    
    echo -n "${NEW_PASSWORD}" > "${SECRETS_DIR}/db_password"
    chmod 400 "${SECRETS_DIR}/db_password"
    
    echo -e "${GREEN}✓${NC} Generated new password"
    
    echo "Updating database..."
    
    OLD_PASSWORD=$(cat "${BACKUP_DIR}"/db_password.* | tail -1)
    
    PGPASSWORD="${OLD_PASSWORD}" psql -h localhost -U gsc_user -d gsc_db -c \
        "ALTER USER gsc_user WITH PASSWORD '${NEW_PASSWORD}';" 2>/dev/null || {
        echo -e "${RED}✗${NC} Failed to update database password"
        echo "Reverting..."
        mv "${BACKUP_DIR}"/db_password.* "${SECRETS_DIR}/db_password" | tail -1
        exit 1
    }
    
    echo -e "${GREEN}✓${NC} Database password updated"
    
    echo "Restarting services..."
    docker-compose restart
    
    echo -e "${GREEN}✓${NC} Services restarted"
    echo ""
    echo -e "${GREEN}Database password rotated successfully${NC}"
}

rotate_api_key() {
    local key_name=$1
    
    echo ""
    echo "Rotating ${key_name}..."
    echo ""
    
    backup_secret "${key_name}"
    
    NEW_KEY=$(openssl rand -hex 32)
    
    echo -n "${NEW_KEY}" > "${SECRETS_DIR}/${key_name}"
    chmod 400 "${SECRETS_DIR}/${key_name}"
    
    echo -e "${GREEN}✓${NC} Generated new ${key_name}"
    
    echo "Restarting services..."
    docker-compose restart
    
    echo -e "${GREEN}✓${NC} Services restarted"
    echo ""
    echo -e "${GREEN}${key_name} rotated successfully${NC}"
    echo ""
    echo -e "${YELLOW}IMPORTANT:${NC} Update API clients with new key:"
    echo "  ${NEW_KEY}"
}

if [ ! -d "${SECRETS_DIR}" ]; then
    echo -e "${RED}✗${NC} Secrets directory not found"
    echo "Run: bash security/setup_secrets.sh"
    exit 1
fi

if [ "$1" == "--all" ]; then
    echo "Rotating all secrets..."
    echo ""
    echo -e "${YELLOW}⚠${NC} This will rotate ALL secrets and restart services"
    read -p "Continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "Aborted"
        exit 0
    fi
    
    rotate_db_password
    rotate_api_key "insights_api_key"
    rotate_api_key "mcp_api_key"
    
    echo ""
    echo "============================================"
    echo -e "${GREEN}All secrets rotated successfully${NC}"
    echo "============================================"
    
elif [ -n "$1" ]; then
    case "$1" in
        db_password)
            rotate_db_password
            ;;
        insights_api_key|mcp_api_key)
            rotate_api_key "$1"
            ;;
        *)
            echo -e "${RED}✗${NC} Unknown secret: $1"
            echo ""
            echo "Available secrets:"
            echo "  - db_password"
            echo "  - insights_api_key"
            echo "  - mcp_api_key"
            exit 1
            ;;
    esac
else
    echo "Usage:"
    echo "  bash security/rotate_secrets.sh [secret_name]"
    echo "  bash security/rotate_secrets.sh --all"
    echo ""
    echo "Available secrets:"
    echo "  - db_password"
    echo "  - insights_api_key"
    echo "  - mcp_api_key"
    exit 1
fi
