#!/bin/bash
# ============================================
# Setup Docker Secrets (OPTIONAL FOR DEV)
# ============================================
# Initializes encrypted secrets for production deployment
# For development, you can use plain .env file instead
# 
# Usage:
#   bash security/setup_secrets.sh [--rotate]

set -e

SECRETS_DIR="./secrets"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "GSC Warehouse - Secrets Setup"
echo "============================================"
echo ""
echo -e "${YELLOW}NOTE:${NC} This is optional for development/localhost"
echo "      For dev, you can use plain .env file instead"
echo ""

generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

generate_api_key() {
    openssl rand -hex 32
}

create_secret_file() {
    local secret_name=$1
    local secret_value=$2
    local secret_file="${SECRETS_DIR}/${secret_name}"
    
    mkdir -p "${SECRETS_DIR}"
    echo -n "${secret_value}" > "${secret_file}"
    chmod 400 "${secret_file}"
    
    echo -e "${GREEN}✓${NC} Created secret: ${secret_name}"
}

check_secret_exists() {
    local secret_name=$1
    [ -f "${SECRETS_DIR}/${secret_name}" ]
}

echo "Checking for existing secrets..."
echo ""

SECRETS_EXIST=false
if [ -d "${SECRETS_DIR}" ] && [ "$(ls -A ${SECRETS_DIR} 2>/dev/null)" ]; then
    SECRETS_EXIST=true
    echo -e "${YELLOW}⚠${NC} Existing secrets found"
    
    if [ "$1" != "--rotate" ]; then
        echo ""
        echo "To rotate secrets, run: bash security/setup_secrets.sh --rotate"
        echo "To keep existing secrets, press Ctrl+C"
        echo ""
        read -p "Overwrite existing secrets? (yes/no): " confirm
        
        if [ "$confirm" != "yes" ]; then
            echo "Aborted"
            exit 0
        fi
    else
        echo -e "${YELLOW}→${NC} Rotating secrets..."
    fi
fi

mkdir -p "${SECRETS_DIR}"

echo ""
echo "Generating secrets..."
echo ""

DB_PASSWORD=$(generate_password)
create_secret_file "db_password" "${DB_PASSWORD}"

DB_READONLY_PASSWORD=$(generate_password)
create_secret_file "db_readonly_password" "${DB_READONLY_PASSWORD}"

DB_APP_PASSWORD=$(generate_password)
create_secret_file "db_app_password" "${DB_APP_PASSWORD}"

INSIGHTS_API_KEY=$(generate_api_key)
create_secret_file "insights_api_key" "${INSIGHTS_API_KEY}"

MCP_API_KEY=$(generate_api_key)
create_secret_file "mcp_api_key" "${MCP_API_KEY}"

if check_secret_exists "slack_webhook_url"; then
    echo -e "${GREEN}✓${NC} Using existing Slack webhook"
else
    echo -e "${YELLOW}→${NC} Enter Slack webhook URL (or press Enter to skip):"
    read -r slack_webhook
    if [ -n "$slack_webhook" ]; then
        create_secret_file "slack_webhook_url" "${slack_webhook}"
    else
        echo -e "${YELLOW}⊘${NC} Skipped Slack webhook"
    fi
fi

if check_secret_exists "jira_api_token"; then
    echo -e "${GREEN}✓${NC} Using existing Jira API token"
else
    echo -e "${YELLOW}→${NC} Enter Jira API token (or press Enter to skip):"
    read -r -s jira_token
    if [ -n "$jira_token" ]; then
        create_secret_file "jira_api_token" "${jira_token}"
        echo ""
    else
        echo ""
        echo -e "${YELLOW}⊘${NC} Skipped Jira API token"
    fi
fi

if check_secret_exists "smtp_password"; then
    echo -e "${GREEN}✓${NC} Using existing SMTP password"
else
    echo -e "${YELLOW}→${NC} Enter SMTP password (or press Enter to skip):"
    read -r -s smtp_password
    if [ -n "$smtp_password" ]; then
        create_secret_file "smtp_password" "${smtp_password}"
        echo ""
    else
        echo ""
        echo -e "${YELLOW}⊘${NC} Skipped SMTP password"
    fi
fi

echo ""
echo "Checking for service account files..."

if [ -f "${SECRETS_DIR}/gsc_sa.json" ]; then
    echo -e "${GREEN}✓${NC} GSC service account exists"
else
    echo -e "${YELLOW}⚠${NC} GSC service account not found"
    echo "   Copy your service account JSON to: ${SECRETS_DIR}/gsc_sa.json"
fi

if [ -f "${SECRETS_DIR}/ga4_sa.json" ]; then
    echo -e "${GREEN}✓${NC} GA4 service account exists"
else
    echo -e "${YELLOW}⚠${NC} GA4 service account not found"
    echo "   Copy your service account JSON to: ${SECRETS_DIR}/ga4_sa.json"
fi

echo ""
echo "============================================"
echo "Secrets Setup Complete"
echo "============================================"
echo ""
echo "Generated secrets:"
echo "  - db_password"
echo "  - db_readonly_password"
echo "  - db_app_password"
echo "  - insights_api_key"
echo "  - mcp_api_key"
echo ""

cat > "${SECRETS_DIR}/.secrets_manifest" << EOF
# Secrets Manifest
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# Rotate by: $(date -u -d "+90 days" +"%Y-%m-%d" 2>/dev/null || date -u -v +90d +"%Y-%m-%d")

db_password
db_readonly_password
db_app_password
insights_api_key
mcp_api_key
EOF

if check_secret_exists "slack_webhook_url"; then
    echo "slack_webhook_url" >> "${SECRETS_DIR}/.secrets_manifest"
fi
if check_secret_exists "jira_api_token"; then
    echo "jira_api_token" >> "${SECRETS_DIR}/.secrets_manifest"
fi
if check_secret_exists "smtp_password"; then
    echo "smtp_password" >> "${SECRETS_DIR}/.secrets_manifest"
fi

echo -e "${GREEN}✓${NC} Secrets manifest created"
echo ""
echo "============================================"
echo "DEPLOYMENT MODE"
echo "============================================"
echo ""
echo "For DEVELOPMENT (localhost):"
echo "  - Use regular docker-compose.yml with .env"
echo "  - Set SECURITY_MODE=development in .env"
echo "  - Secrets are optional"
echo ""
echo "For PRODUCTION:"
echo "  - Use docker-compose -f docker-compose.secrets.yml"
echo "  - Set SECURITY_MODE=production"
echo "  - Secrets are required"
echo ""
