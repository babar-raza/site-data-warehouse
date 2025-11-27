#!/bin/bash
# Pre-deployment validation script
# Checks prerequisites before running deployment

echo "========================================"
echo "Pre-Deployment Validation"
echo "========================================"
echo ""

errors=0
warnings=0

# Check 1: Docker
echo "[1/8] Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "  ❌ Docker not found or not in PATH"
    ((errors++))
else
    docker --version
    echo "  ✓ Docker is installed"
fi
echo ""

# Check 2: Docker running
echo "[2/8] Checking if Docker is running..."
if ! docker info > /dev/null 2>&1; then
    echo "  ❌ Docker is not running - Please start Docker"
    ((errors++))
else
    echo "  ✓ Docker is running"
fi
echo ""

# Check 3: Docker Compose
echo "[3/8] Checking Docker Compose..."
if ! docker compose version > /dev/null 2>&1; then
    echo "  ❌ Docker Compose not found"
    ((errors++))
else
    docker compose version
    echo "  ✓ Docker Compose is available"
fi
echo ""

# Check 4: Required files
echo "[4/8] Checking required files..."
missing=0

if [ ! -f "docker-compose.yml" ]; then
    echo "  ❌ docker-compose.yml not found"
    ((missing++))
fi

if [ ! -f "requirements.txt" ]; then
    echo "  ❌ requirements.txt not found"
    ((missing++))
fi

if [ ! -f ".env" ]; then
    echo "  ⚠ .env not found - will be created from .env.example"
    ((warnings++))
fi

if [ $missing -gt 0 ]; then
    echo "  ❌ Missing $missing required file(s)"
    ((errors++))
else
    echo "  ✓ All required files present"
fi
echo ""

# Check 5: Secrets
echo "[5/8] Checking secrets..."
if [ ! -f "secrets/gsc_sa.json" ]; then
    echo "  ⚠ secrets/gsc_sa.json not found"
    echo "    You will need to add this file with your GCP credentials"
    ((warnings++))
else
    echo "  ✓ secrets/gsc_sa.json exists"
fi

if [ ! -f "secrets/db_password.txt" ]; then
    echo "  ⚠ secrets/db_password.txt not found"
    echo "    Default password will be used"
    ((warnings++))
else
    echo "  ✓ secrets/db_password.txt exists"
fi
echo ""

# Check 6: Directories
echo "[6/8] Checking directory structure..."
dir_errors=0

if [ ! -d "compose/dockerfiles" ]; then
    echo "  ❌ Missing dockerfiles directory"
    ((dir_errors++))
fi

if [ ! -d "ingestors" ]; then
    echo "  ❌ Missing ingestors directory"
    ((dir_errors++))
fi

if [ ! -d "sql" ]; then
    echo "  ❌ Missing sql directory"
    ((dir_errors++))
fi

if [ $dir_errors -gt 0 ]; then
    ((errors+=dir_errors))
else
    echo "  ✓ Directory structure is valid"
fi
echo ""

# Check 7: Docker resources
echo "[7/8] Checking Docker resources..."
if docker info | grep -q "Total Memory"; then
    echo "  ✓ Docker resources available"
else
    echo "  ⚠ Unable to check Docker memory allocation"
    ((warnings++))
fi
echo ""

# Check 8: Network connectivity
echo "[8/8] Checking network connectivity..."
if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "  ✓ Internet connectivity available"
else
    echo "  ⚠ No internet connectivity detected"
    echo "    Required for downloading Docker images"
    ((warnings++))
fi
echo ""

# Summary
echo "========================================"
echo "Validation Summary"
echo "========================================"
echo ""

if [ $errors -eq 0 ]; then
    if [ $warnings -eq 0 ]; then
        echo "✓ All checks passed! Ready to deploy."
        echo ""
        echo "Run: ./deploy.sh"
    else
        echo "⚠ $warnings warning(s) found"
        echo ""
        echo "You can proceed with deployment, but you may need to:"
        echo "  - Add secrets/gsc_sa.json with your GCP credentials"
        echo "  - Configure .env with your project settings"
        echo ""
        echo "Run: ./deploy.sh"
    fi
else
    echo "❌ $errors error(s) found"
    echo ""
    echo "Please fix the errors above before deploying."
    echo ""
fi

if [ $warnings -gt 0 ]; then
    echo ""
    echo "⚠ Warnings:"
    echo "  - Missing secrets will use placeholders (won't connect to real data)"
    echo "  - Missing .env will be created from .env.example"
    echo ""
fi

exit $errors
