# Repository Cleanup & Safe-Sharing Plan

**Project**: SEO Intelligence Platform / Site Data Warehouse
**Language/Runtime**: Python 3.11+
**Build Tools**: Docker, Docker Compose, pip
**Frameworks**: FastAPI, Celery, PostgreSQL, Redis, Prometheus, Grafana
**Generated**: 2025-11-27

---

## Table of Contents

1. [Critical Items to Remove BEFORE Committing](#1-critical-items-to-remove-before-committing)
2. [Folder-by-Folder Cleanup Strategies](#2-folder-by-folder-cleanup-strategies)
3. [Additional Folders to Clean or Exclude](#3-additional-folders-to-clean-or-exclude)
4. [Production-Quality .gitignore](#4-production-quality-gitignore)
5. [Safe-Sharing Checklist](#5-safe-sharing-checklist)
6. [Final Recommended Repository Structure](#6-final-recommended-repository-structure)
7. [Step-by-Step Execution Guide](#7-step-by-step-execution-guide)

---

## 1. Critical Items to Remove BEFORE Committing

### 1.1 IMMEDIATE DELETION REQUIRED (Contains Secrets)

| Item | Risk Level | Action |
|------|------------|--------|
| `/secrets/gsc_sa.json` | **CRITICAL** | DELETE - Contains GCP service account private key |
| `/secrets/gsc-bigdata-476706-bb35128e94ad.json` | **CRITICAL** | DELETE - Contains GCP credentials with project ID |
| `/secrets/db_password.txt` | **CRITICAL** | DELETE - Contains database password |
| `.env` | **CRITICAL** | DELETE - Contains all environment secrets |
| `.env.production.template` | **HIGH** | REVIEW - May contain real values |
| `.env.secure.example` | **HIGH** | REVIEW - Ensure only placeholders |
| `.claude/settings.local.json` | **MEDIUM** | DELETE - Machine-specific Claude settings |

### 1.2 Machine-Generated & Cache Files

| Item | Risk Level | Action |
|------|------------|--------|
| `__pycache__/` (all locations) | LOW | DELETE - Python bytecode cache |
| `.mypy_cache/` | LOW | DELETE - Type checker cache |
| `.pytest_cache/` | LOW | DELETE - Test runner cache |
| `htmlcov/` | LOW | DELETE - Coverage HTML reports |
| `coverage.xml` | LOW | DELETE - Coverage data |
| `.coverage` | LOW | DELETE - Coverage data |
| `=1.0.0` | LOW | DELETE - Malformed pip artifact |
| `nul` | LOW | DELETE - Windows null device artifact |
| `logs/*.log` | MEDIUM | DELETE - May contain sensitive runtime data |
| `logs/scheduler_metrics.json` | MEDIUM | DELETE - Runtime metrics |

### 1.3 IDE/Editor Configuration

| Item | Action | Notes |
|------|--------|-------|
| `.vscode/` | DELETE or REVIEW | Contains `settings.json` - may have machine paths |
| `.idea/` | DELETE | JetBrains IDE (if exists) |
| `*.swp`, `*.swo`, `*~` | DELETE | Vim/editor swap files |
| `.DS_Store` | DELETE | macOS folder metadata |
| `Thumbs.db` | DELETE | Windows thumbnail cache |

### 1.4 Sensitive Information Categories Identified

```
Category                          Files Found    Risk
--------------------------------  -------------  --------
GCP Service Account Keys          2              CRITICAL
Database Credentials              1              CRITICAL
Environment Variables             4              CRITICAL
API Keys in Code (patterns)       37 files       HIGH (review each)
Internal Project Reports          40+            MEDIUM
Phase Implementation Plans        15+            MEDIUM
Test Coverage Reports             5+             LOW
```

---

## 2. Folder-by-Folder Cleanup Strategies

### 2.1 `docs/` Folder Cleanup

**Current State**: Messy, duplicated content across subfolders, mix of user guides and internal analysis.

#### Files to Archive Privately (Move to private backup)
```
docs/analysis/PROJECT_STRUCTURE.txt    # Internal project analysis
docs/analysis/SCRIPTS.txt              # Internal script documentation
docs/analysis/STRUCTURE.txt            # Internal structure notes
docs/archive/                          # Already archived - review contents
```

#### Files to Keep (Safe for public)
```
docs/ARCHITECTURE.md                   # Technical architecture overview
docs/ARCHITECTURE_PATTERNS.md          # Design patterns documentation
docs/DEPLOYMENT.md                     # Deployment guide
docs/QUICKSTART.md                     # Quick start guide
docs/TROUBLESHOOTING.md               # Troubleshooting guide
docs/INDEX.md                          # Documentation index
docs/api/                              # API documentation
docs/runbooks/                         # Operations runbooks
```

#### Files to Review Carefully
```
docs/GSC_SERP_TRACKING.md             # Check for API key examples
docs/SERP_TRACKING_GUIDE.md           # Check for API key examples
docs/PAGESPEED_SETUP.md               # Check for credential examples
docs/QUICK_REFERENCE.md               # Check for sensitive config
docs/QUICK_REFERENCE_CSE_INTEGRATION.md  # Check for API examples
docs/guides/                          # Review each file
docs/implementation/                   # Review for internal notes
docs/testing/                         # Review for internal test data
docs/deployment/                      # Review for credentials
docs/system-architecture.png          # KEEP - Visual diagram
```

#### Files to Merge/Consolidate
```
# Merge these into single comprehensive guides:
docs/analysis/DASHBOARD_GUIDE.md      → docs/guides/DASHBOARD_GUIDE.md
docs/analysis/INSIGHT_ENGINE_GUIDE.md → docs/guides/INSIGHT_ENGINE_GUIDE.md
docs/analysis/SYSTEM_OVERVIEW.md      → docs/ARCHITECTURE.md (merge)
docs/analysis/TECHNICAL_ARCHITECTURE.md → docs/ARCHITECTURE.md (merge)
docs/analysis/MULTI_AGENT_SYSTEM.md   → docs/guides/MULTI_AGENT_SYSTEM.md
```

#### Recommended Final Structure for `docs/`
```
docs/
├── ARCHITECTURE.md                    # Merged from multiple sources
├── DEPLOYMENT.md
├── QUICKSTART.md
├── TROUBLESHOOTING.md
├── INDEX.md
├── system-architecture.png
├── api/
│   └── [API documentation files]
├── guides/
│   ├── DASHBOARD_GUIDE.md
│   ├── INSIGHT_ENGINE_GUIDE.md
│   ├── MULTI_AGENT_SYSTEM.md
│   ├── GSC_INTEGRATION.md
│   ├── GA4_INTEGRATION.md
│   ├── SERP_TRACKING.md
│   └── MCP_INTEGRATION.md
└── runbooks/
    └── [Operational runbooks]
```

---

### 2.2 `reports/` Folder Cleanup

**Current State**: Contains internal working notes, implementation reports, phase summaries, and announcement drafts - NOT suitable for public sharing.

#### Files to Archive Privately (ALL should be archived)
```
reports/analysis.md                    # Internal analysis
reports/annoucenment.md               # Draft announcement
reports/announce.md                    # Draft announcement
reports/announcement.html              # Draft announcement
reports/BLOG_POST_ANNOUNCEMENT.md     # Internal marketing draft
reports/CHANGELOG.md                   # Move to root if sanitized
reports/COVERAGE_SUMMARY.md           # Internal test coverage
reports/coverage-baseline.txt         # Test metrics
reports/coverage-final.txt            # Test metrics
reports/DASHBOARD_COMPLETION_REPORT.md # Internal project report
reports/DOCKER_DEPLOYMENT_SUMMARY.md  # Internal deployment notes
reports/docker_optimization.md        # Internal optimization notes
reports/DOCKER_SETUP_README.md        # Internal setup notes
reports/final-summary.md              # Internal summary
reports/GA4_DASHBOARD_FIXES.md        # Internal fixes
reports/GA4_IMPLEMENTATION_CHECKLIST.md # Internal checklist
reports/GRAFANA_TROUBLESHOOTING.md    # Move to docs/troubleshooting/
reports/insight_engine.md             # Internal analysis
reports/MARKDOWN_REORGANIZATION_SUMMARY.md # Internal notes
reports/non_code_tidiness_report.md   # Internal audit
reports/phase-1.md through phase-4.md # Internal planning
reports/phase-3-4-5.md                # Internal planning
reports/PROJECT_COMPLETE_SUMMARY.md   # Internal summary
reports/PROJECT_SUMMARY.md            # Internal summary
reports/SYSTEM_OVERVIEW.md            # Duplicate - exists in docs/
reports/SYSTEM_TIDINESS_REPORT.md     # Internal audit
reports/TASKCARD-*.md                 # Internal task tracking
reports/TEST_COVERAGE_REPORT.md       # Internal test report
reports/TEST_UPGRADE_SUMMARY.md       # Internal upgrade notes
reports/TESTING_LOCALHOST.md          # Internal testing notes
reports/TESTING_UPGRADE_COMPLETE.md   # Internal upgrade notes
reports/ui_test_coverage.md           # Internal test coverage
reports/archive/                       # Archive entire subfolder
```

#### Recommended Action for `reports/`
```bash
# Create private archive directory (outside repo)
mkdir -p ~/private-archives/site-data-warehouse-reports-backup

# Move entire reports folder to private archive
cp -r reports/ ~/private-archives/site-data-warehouse-reports-backup/

# Remove reports folder from repo
rm -rf reports/

# Create minimal public reports structure if needed
mkdir -p reports
echo "# Reports\n\nThis folder contains generated reports from system operations." > reports/README.md
```

#### What to Keep (if any)
```
reports/CHANGELOG.md → Move to root as CHANGELOG.md (after review)
reports/README.md → Keep as placeholder
```

---

### 2.3 `plans/` Folder Cleanup

**Current State**: Contains detailed implementation plans, task cards, and internal project management documents.

#### Files to Archive Privately (ALL should be archived)
```
plans/automated_testing.md            # 46KB - Internal testing plans
plans/automated_testing_taskcards.md  # 51KB - Internal task tracking
plans/docker-optimization.md          # 28KB - Internal optimization
plans/docker-service-configuration-fixes.md # Internal fixes
plans/docker-testing-and-fixes.md     # Internal testing notes
plans/E2E_TEST_PLAN.md               # Internal test planning
plans/enhacements.md                  # Internal enhancement plans
plans/ga4_implementation.md           # 51KB - Implementation details
plans/grafana-dashboard-data-fixes.md # Internal fixes
plans/insight_engine.md               # 135KB - Major internal docs
plans/insight_engine_requirements_extraction.md # Internal analysis
plans/insight_engine_taskcards.md     # 131KB - Task tracking
plans/insight_engine_taskcards_prompt.md # Internal prompts
plans/insights.md                     # 157KB - Internal analysis
plans/prometheus_ui_enhancement.md    # Internal UI plans
plans/service-fixes-plan.md           # Internal fixes
plans/taskcards.md                    # 429KB - All task cards
plans/ui_test_coverage.md             # Internal test coverage
```

#### Recommended Action for `plans/`
```bash
# Create private archive
mkdir -p ~/private-archives/site-data-warehouse-plans-backup
cp -r plans/ ~/private-archives/site-data-warehouse-plans-backup/

# Remove from repo entirely
rm -rf plans/

# DO NOT create a public plans/ folder - implementation details are internal
```

---

### 2.4 `deployment/` Folder Cleanup

**Current State**: Well-organized with guides and platform-specific scripts. Review needed for credential examples.

#### Current Structure
```
deployment/
├── README.md
├── docker/
├── guides/
├── linux/
└── windows/
```

#### Files to Review for Credentials
```
deployment/guides/                    # Check each guide for API key examples
deployment/docker/                    # Check for hardcoded values
deployment/linux/                     # Check shell scripts for secrets
deployment/windows/                   # Check batch files for secrets
```

#### Recommended Actions
1. Review `deployment/README.md` for any hardcoded paths or credentials
2. Ensure all credential references use placeholders like `YOUR_API_KEY_HERE`
3. Verify scripts use environment variables, not hardcoded values

#### Files to Keep (after review)
```
deployment/                           # KEEP entire folder after review
```

---

### 2.5 `secrets/` Folder - CRITICAL

**Current State**: Contains ACTUAL credentials - MUST be completely excluded.

#### Immediate Actions Required
```bash
# 1. NEVER commit this folder
# 2. Ensure it's in .gitignore
# 3. Create template files only

# Keep only templates:
secrets/gsc_sa.json.template          # KEEP - Template with placeholders
secrets/README.md                     # KEEP - Instructions only

# DELETE these files:
secrets/gsc_sa.json                   # DELETE - Real credentials
secrets/gsc-bigdata-476706-bb35128e94ad.json  # DELETE - Real credentials
secrets/db_password.txt               # DELETE - Real password
```

---

## 3. Additional Folders to Clean or Exclude

### 3.1 Folders to ADD to .gitignore

| Folder/File | Reason | Action |
|-------------|--------|--------|
| `/secrets/` | Contains credentials | Already in gitignore - verify |
| `.env` | Environment variables | Already in gitignore - verify |
| `*.env` | Any env files | Already in gitignore |
| `__pycache__/` | Python cache | Already in gitignore |
| `.mypy_cache/` | Type checker | ADD to gitignore |
| `.pytest_cache/` | Test cache | Already in gitignore |
| `htmlcov/` | Coverage reports | ADD to gitignore |
| `coverage.xml` | Coverage data | ADD to gitignore |
| `.coverage` | Coverage data | Already in gitignore |
| `logs/` | Runtime logs | Already partial - expand |
| `.vscode/` | IDE settings | Already in gitignore |
| `.idea/` | IDE settings | Already in gitignore |
| `.claude/` | Claude Code settings | ADD to gitignore |
| `nul` | Windows artifact | Already in gitignore |
| `=1.0.0` | Malformed pip | ADD pattern |
| `reports/` | Internal reports | ADD to gitignore (entire folder) |
| `plans/` | Internal plans | ADD to gitignore (entire folder) |
| `*.bak` | Backup files | Already in gitignore |
| `.dockerignore.bak` | Backup file | DELETE or gitignore |

### 3.2 Files to Review in Root Directory

| File | Action | Notes |
|------|--------|-------|
| `README.md` | REVIEW | Ensure no credentials, internal URLs |
| `bootstrap.py` | REVIEW | Check for hardcoded values |
| `docker-compose.yml` | REVIEW | Check for secrets (should use env vars) |
| `docker-compose.dev.yml` | REVIEW | Development config |
| `docker-compose.prod.yml` | REVIEW | Production config |
| `docker-compose.secrets.yml` | REVIEW | May reference secrets incorrectly |
| `.dockerignore` | KEEP | Already has exclusions |
| `.dockerignore.bak` | DELETE | Backup file |
| `mypy.ini` | KEEP | Type checking config |
| `pytest.ini` | KEEP | Test config |
| `requirements.txt` | KEEP | Dependencies |
| `requirements-test.txt` | KEEP | Test dependencies |

### 3.3 Additional Cleanup Recommendations

```bash
# Delete these artifacts from root:
rm -f "=1.0.0"                        # Malformed pip artifact
rm -f nul                             # Windows null device artifact
rm -f .dockerignore.bak               # Backup file

# Clean Python caches:
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null

# Clean coverage artifacts:
rm -rf htmlcov/
rm -f coverage.xml
rm -f .coverage
```

---

## 4. Production-Quality .gitignore

Replace your current `.gitignore` with this comprehensive version:

```gitignore
# =============================================================================
# SEO Intelligence Platform - .gitignore
# =============================================================================
# This file excludes sensitive, generated, and machine-specific files from
# version control. Review before committing to ensure no secrets are exposed.
# =============================================================================

# =============================================================================
# SECRETS & CREDENTIALS (CRITICAL - NEVER COMMIT)
# =============================================================================
/secrets/
!secrets/README.md
!secrets/*.template
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
*_rsa
*_dsa
*_ecdsa
*_ed25519
*.gpg
credentials.json
**/credentials.json
service_account*.json
**/service_account*.json
*-sa.json
**/*-sa.json
gsc_sa.json
ga4_sa.json
**/gsc-*.json
db_password*
api_key*
secret*
!secrets/

# =============================================================================
# INTERNAL DOCUMENTATION (NOT FOR PUBLIC SHARING)
# =============================================================================
/reports/
!/reports/README.md
!/reports/CHANGELOG.md
/plans/
*.internal.md
*_INTERNAL.md
TASKCARD*.md

# =============================================================================
# PYTHON
# =============================================================================
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/
pytest_cache/
test-results/
test_output/
tests/outputs/

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json
.pyre/
.pytype/

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/
pythonenv*/

# =============================================================================
# IDE & EDITORS
# =============================================================================
# VSCode
.vscode/
*.code-workspace

# JetBrains
.idea/
*.iml
*.iws
*.ipr

# Vim
*.swp
*.swo
*~
.netrwhist

# Emacs
*~
\#*\#
/.emacs.desktop
/.emacs.desktop.lock
*.elc
auto-save-list
tramp
.\#*

# Sublime Text
*.sublime-workspace
*.sublime-project

# Claude Code
.claude/
!.claude/settings.json.example

# =============================================================================
# OS FILES
# =============================================================================
# macOS
.DS_Store
.AppleDouble
.LSOverride
._*
.Spotlight-V100
.Trashes

# Windows
Thumbs.db
Thumbs.db:encryptable
ehthumbs.db
ehthumbs_vista.db
*.stackdump
[Dd]esktop.ini
$RECYCLE.BIN/
*.cab
*.msi
*.msix
*.msm
*.msp
*.lnk
nul

# Linux
*~
.fuse_hidden*
.directory
.Trash-*
.nfs*

# =============================================================================
# DOCKER
# =============================================================================
docker-compose.override.yml
.docker/

# =============================================================================
# LOGS & TEMPORARY FILES
# =============================================================================
logs/
*.log
*.log.*
npm-debug.log*
yarn-debug.log*
yarn-error.log*
lerna-debug.log*
.pnpm-debug.log*

# Temporary files
*.tmp
*.temp
*.bak
*.backup
*.swp
*.orig
tmp/
temp/
.temp/

# =============================================================================
# DATA & SAMPLES
# =============================================================================
# Large data files
*.csv
!samples/*.csv
*.parquet
*.feather
data/
!data/README.md

# Database files
*.db
*.sqlite
*.sqlite3
*.sql.gz

# =============================================================================
# BUILD ARTIFACTS
# =============================================================================
=1.0.0
*.whl

# =============================================================================
# MONITORING & METRICS
# =============================================================================
*.metrics.json
scheduler_metrics.json

# =============================================================================
# TERRAFORM & INFRASTRUCTURE (if applicable)
# =============================================================================
*.tfstate
*.tfstate.*
.terraform/
*.tfvars
!*.tfvars.example
crash.log
crash.*.log
override.tf
override.tf.json
*_override.tf
*_override.tf.json
.terraformrc
terraform.rc

# =============================================================================
# KUBERNETES (if applicable)
# =============================================================================
kubeconfig
*.kubeconfig
```

---

## 5. Safe-Sharing Checklist

### 5.1 Pre-Publication Security Scan

Run these commands before publishing:

```bash
# Install scanning tools
pip install trufflehog
pip install detect-secrets

# Option 1: TruffleHog - Scan for secrets in history
trufflehog git file://. --only-verified

# Option 2: detect-secrets - Scan current files
detect-secrets scan . > .secrets.baseline

# Option 3: gitleaks (if installed)
gitleaks detect --source . --verbose

# Option 4: git-secrets (if installed)
git secrets --scan
```

### 5.2 Git History Cleanup

If secrets were previously committed:

```bash
# WARNING: This rewrites history - coordinate with team

# Option 1: BFG Repo Cleaner (recommended)
java -jar bfg.jar --delete-files "*.json" --delete-files ".env" .

# Option 2: git filter-branch (slower)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch secrets/gsc_sa.json' \
  --prune-empty --tag-name-filter cat -- --all

# After cleaning, force push (if remote exists)
git push origin --force --all
git push origin --force --tags
```

### 5.3 Pre-Publication Checklist

| # | Check | Command/Action | Status |
|---|-------|----------------|--------|
| 1 | Remove all files in `/secrets/` except templates | `rm secrets/*.json secrets/*.txt` (keep .template) | [ ] |
| 2 | Delete `.env` file | `rm .env` | [ ] |
| 3 | Verify `.env.example` has only placeholders | Manual review | [ ] |
| 4 | Delete `/reports/` folder | `rm -rf reports/` | [ ] |
| 5 | Delete `/plans/` folder | `rm -rf plans/` | [ ] |
| 6 | Delete `/htmlcov/` folder | `rm -rf htmlcov/` | [ ] |
| 7 | Delete `coverage.xml` | `rm coverage.xml` | [ ] |
| 8 | Delete `/.claude/` folder | `rm -rf .claude/` | [ ] |
| 9 | Delete `/.vscode/` folder | `rm -rf .vscode/` | [ ] |
| 10 | Delete cache folders | `find . -name "__pycache__" -exec rm -rf {} +` | [ ] |
| 11 | Delete `.mypy_cache/` | `rm -rf .mypy_cache/` | [ ] |
| 12 | Delete `/logs/` contents | `rm -rf logs/*` | [ ] |
| 13 | Delete malformed artifacts | `rm -f "=1.0.0" nul .dockerignore.bak` | [ ] |
| 14 | Run secret scanner | `trufflehog git file://.` | [ ] |
| 15 | Review all `.md` files for credentials | Manual grep for API keys | [ ] |
| 16 | Review `docker-compose*.yml` for hardcoded secrets | Manual review | [ ] |
| 17 | Review Python files for hardcoded credentials | `grep -r "api_key\|password\|secret" --include="*.py"` | [ ] |
| 18 | Verify `.gitignore` is comprehensive | Compare with Section 4 | [ ] |
| 19 | Check image files for sensitive screenshots | Manual review of `.png`, `.jpg` | [ ] |
| 20 | Review third-party licenses | Check `requirements.txt` dependencies | [ ] |

### 5.4 Documentation Review Checklist

| # | Check | Files to Review |
|---|-------|-----------------|
| 1 | No internal URLs (company intranet, internal tools) | All `.md` files |
| 2 | No employee names or emails | All `.md` files |
| 3 | No internal project codes/IDs | All `.md` files |
| 4 | No customer data examples | `samples/`, `tests/fixtures/` |
| 5 | No production server addresses | All config files |
| 6 | No internal IP addresses | All config files |
| 7 | Example credentials use placeholders | All documentation |

### 5.5 File Metadata Check

```bash
# Check for metadata in images (may contain GPS, device info)
exiftool docs/system-architecture.png

# Strip metadata from images before committing
exiftool -all= docs/system-architecture.png
```

---

## 6. Final Recommended Repository Structure

After cleanup, your repository should look like this:

```
site-data-warehouse/
├── .github/
│   └── workflows/
│       └── [CI/CD workflows]
├── agents/
│   ├── base/
│   ├── diagnostician/
│   ├── dispatcher/
│   ├── orchestration/
│   ├── strategist/
│   └── watcher/
├── automation/
├── compose/
│   └── dockerfiles/
├── config/
│   ├── alert_rules.example.yaml
│   ├── application.example.yaml
│   ├── scheduler_config.yaml
│   └── [other config templates]
├── deployment/
│   ├── README.md
│   ├── docker/
│   ├── guides/
│   ├── linux/
│   └── windows/
├── docs/
│   ├── INDEX.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   ├── QUICKSTART.md
│   ├── TROUBLESHOOTING.md
│   ├── system-architecture.png
│   ├── api/
│   ├── guides/
│   └── runbooks/
├── examples/
├── grafana/
│   └── provisioning/
│       ├── dashboards/
│       └── datasources/
├── ingestors/
│   ├── api/
│   ├── ga4/
│   └── trends/
├── insights_api/
│   └── routes/
├── insights_core/
│   ├── channels/
│   └── detectors/
├── mcp/
├── metrics_exporter/
├── notifications/
├── prometheus/
├── requirements/
├── samples/
│   ├── README.md
│   ├── ga4_sample_data.csv
│   ├── gsc_sample_data.csv
│   └── sample_insights.json
├── scheduler/
├── scripts/
│   ├── README.md
│   ├── operations/
│   └── setup/
├── secrets/
│   ├── README.md
│   └── gsc_sa.json.template
├── security/
├── services/
├── sql/
├── tests/
│   ├── agents/
│   ├── dashboards/
│   ├── e2e/
│   ├── ingestors/
│   ├── insights_api/
│   ├── insights_core/
│   ├── integration/
│   └── [other test directories]
├── transform/
├── warehouse/
├── .dockerignore
├── .env.example
├── .gitignore
├── bootstrap.py
├── CHANGELOG.md                    # (moved from reports/)
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── LICENSE                         # (add if missing)
├── mypy.ini
├── pytest.ini
├── README.md
├── requirements.txt
└── requirements-test.txt
```

### Folders REMOVED from public repository:
- `reports/` - Archived privately
- `plans/` - Archived privately
- `docs/analysis/` - Merged into main docs
- `htmlcov/` - Generated coverage
- `logs/` - Runtime logs (empty placeholder OK)
- `.claude/` - Claude Code config
- `.vscode/` - IDE config
- `__pycache__/` - All instances
- `.mypy_cache/` - Type checker cache
- `.pytest_cache/` - Test cache

---

## 7. Step-by-Step Execution Guide

Execute these steps IN ORDER:

### Step 1: Create Private Backup (5 minutes)

```bash
# Create backup directory outside the repo
mkdir -p ~/private-archives/site-data-warehouse-$(date +%Y%m%d)

# Backup sensitive folders
cp -r secrets/ ~/private-archives/site-data-warehouse-$(date +%Y%m%d)/secrets-backup/
cp -r reports/ ~/private-archives/site-data-warehouse-$(date +%Y%m%d)/reports-backup/
cp -r plans/ ~/private-archives/site-data-warehouse-$(date +%Y%m%d)/plans-backup/
cp .env ~/private-archives/site-data-warehouse-$(date +%Y%m%d)/.env.backup 2>/dev/null || true
```

### Step 2: Delete Critical Secrets (2 minutes)

```bash
cd "c:/Users/prora/OneDrive/Documents/GitHub/site-data-warehouse"

# Delete actual credential files (keep templates)
rm -f secrets/gsc_sa.json
rm -f secrets/gsc-bigdata-476706-bb35128e94ad.json
rm -f secrets/db_password.txt
rm -f .env
rm -f .env.production.template  # Review first - delete if contains real values
```

### Step 3: Delete Internal Documentation (2 minutes)

```bash
# Remove entire internal folders
rm -rf reports/
rm -rf plans/

# Create placeholder if needed
mkdir -p reports
echo "# Reports\n\nGenerated reports are not committed to version control." > reports/README.md
```

### Step 4: Delete Generated/Cache Files (2 minutes)

```bash
# Delete coverage and cache
rm -rf htmlcov/
rm -f coverage.xml
rm -f .coverage

# Delete Python caches
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -rf .mypy_cache/
rm -rf .pytest_cache/

# Delete IDE config
rm -rf .claude/
rm -rf .vscode/

# Delete artifacts
rm -f "=1.0.0"
rm -f nul
rm -f .dockerignore.bak

# Clean logs (keep directory)
rm -f logs/*.log
rm -f logs/*.json
```

### Step 5: Update .gitignore (2 minutes)

```bash
# Replace .gitignore with the comprehensive version from Section 4
# (Copy the content from Section 4 into .gitignore)
```

### Step 6: Consolidate Documentation (10 minutes)

```bash
# Merge analysis docs into main guides
# Manual process - review and merge:
# - docs/analysis/SYSTEM_OVERVIEW.md → docs/ARCHITECTURE.md
# - docs/analysis/TECHNICAL_ARCHITECTURE.md → docs/ARCHITECTURE.md
# - docs/analysis/DASHBOARD_GUIDE.md → docs/guides/DASHBOARD_GUIDE.md
# etc.

# After merging, remove analysis folder
rm -rf docs/analysis/
```

### Step 7: Run Security Scan (5 minutes)

```bash
# Install if needed
pip install trufflehog detect-secrets

# Scan for secrets
trufflehog git file://. --only-verified

# Scan current state
detect-secrets scan .
```

### Step 8: Review Flagged Files (15-30 minutes)

Review each of the 37 Python files flagged for potential credential patterns:
- Most will be test files with mock credentials (OK)
- Check any that use `os.getenv()` or config files (should be OK)
- Flag any with hardcoded real values (FIX)

### Step 9: Final Verification (5 minutes)

```bash
# List all files that would be committed
git status

# Verify no secrets in staged files
git diff --cached | grep -i -E "(api_key|password|secret|token)" || echo "No obvious secrets found"

# Dry run of what would be ignored
git check-ignore -v *
```

### Step 10: Commit Cleanup (2 minutes)

```bash
# Stage all changes
git add .

# Commit cleanup
git commit -m "chore: repository cleanup for public sharing

- Remove sensitive credentials and secrets
- Remove internal reports and planning documents
- Update .gitignore with comprehensive exclusions
- Consolidate documentation structure
- Remove generated/cache files"
```

---

## Summary of Actions

| Category | Items | Action |
|----------|-------|--------|
| **CRITICAL - Delete** | 3 credential files, .env | Immediate deletion |
| **High Priority** | reports/, plans/ folders | Archive privately, remove from repo |
| **Medium Priority** | htmlcov/, caches, IDE config | Delete |
| **Low Priority** | Consolidate docs | Merge and reorganize |
| **Configuration** | .gitignore | Replace with comprehensive version |
| **Verification** | Security scan | Run before publishing |

---

**Document Generated**: 2025-11-27
**Review Before**: Publishing to GitHub or GitLab
**Author**: Claude Code Assistant
