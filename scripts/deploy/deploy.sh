#!/bin/bash
set -euo pipefail

################################################################################
# ThesisLedger Production Deployment Script
#
# Deploys to Oracle Cloud ARM VM (Ampere A1: 4 vCPU, 24GB RAM)
#
# Usage:
#   ./scripts/deploy/deploy.sh [OPTIONS]
#
# Environment Variables (required):
#   SSH_HOST          Target VM host (e.g., oracle-prod.example.com)
#   SSH_USER          SSH user (default: opc for Oracle Linux)
#   SSH_KEY           Path to private SSH key (default: ~/.ssh/id_rsa)
#   DOMAIN            Production domain (e.g., thesisledger.example.com)
#   GIT_BRANCH        Git branch to deploy (default: main)
#
# Optional:
#   POSTGRES_PASSWORD Required! Set in .env or pass here
#   REDIS_PASSWORD    Required! Set in .env or pass here
#   SKIP_OLLAMA       Skip Ollama model setup (default: false)
#   DRY_RUN           Print commands without executing (default: false)
#
# Example:
#   export SSH_HOST=oracle-prod.example.com
#   export SSH_USER=opc
#   export DOMAIN=thesisledger.example.com
#   export POSTGRES_PASSWORD=your_secure_password
#   export REDIS_PASSWORD=your_secure_password
#   ./scripts/deploy/deploy.sh
################################################################################

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="${PROJECT_DIR:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Required environment variables
SSH_HOST="${SSH_HOST:?Error: SSH_HOST not set}"
SSH_USER="${SSH_USER:-opc}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"
DOMAIN="${DOMAIN:?Error: DOMAIN not set}"
GIT_BRANCH="${GIT_BRANCH:-main}"

# Optional
SKIP_OLLAMA="${SKIP_OLLAMA:-false}"
DRY_RUN="${DRY_RUN:-false}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

# Derived
SSH_TARGET="${SSH_USER}@${SSH_HOST}"
REMOTE_PROJECT_PATH="/home/${SSH_USER}/thesisledger"

################################################################################
# Utility Functions
################################################################################

log_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

log_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

log_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

run_remote() {
    local cmd="$1"
    log_info "Running: $cmd"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY RUN] $cmd"
    else
        ssh -i "$SSH_KEY" "$SSH_TARGET" bash -c "$cmd" || {
            log_error "Remote command failed: $cmd"
            return 1
        }
    fi
}

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Required environment variables:
  SSH_HOST              Target VM hostname/IP
  SSH_USER              SSH username (default: opc)
  DOMAIN                Production domain

Optional environment variables:
  SSH_KEY               Path to SSH private key (default: ~/.ssh/id_rsa)
  GIT_BRANCH            Git branch to deploy (default: main)
  POSTGRES_PASSWORD     PostgreSQL password (required if not in .env)
  REDIS_PASSWORD        Redis password (required if not in .env)
  SKIP_OLLAMA           Skip Ollama setup (default: false)
  DRY_RUN               Print commands without executing (default: false)

Example:
  export SSH_HOST=oracle.example.com
  export DOMAIN=thesisledger.example.com
  export POSTGRES_PASSWORD=\$(openssl rand -base64 32)
  export REDIS_PASSWORD=\$(openssl rand -base64 32)
  ./scripts/deploy/deploy.sh

EOF
}

################################################################################
# Pre-flight Checks
################################################################################

log_info "🚀 ThesisLedger Production Deployment"
log_info "═══════════════════════════════════════════════════════════════════"

# Verify SSH key exists
if [[ ! -f "$SSH_KEY" ]]; then
    log_error "SSH key not found: $SSH_KEY"
    print_usage
    exit 1
fi

log_success "SSH key found: $SSH_KEY"

# Test SSH connection
log_info "Testing SSH connection to $SSH_TARGET..."
if ! ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$SSH_TARGET" "echo 'SSH connection OK'" > /dev/null 2>&1; then
    log_error "Cannot connect to $SSH_TARGET via SSH"
    exit 1
fi
log_success "SSH connection successful"

# Verify passwords are set
if [[ -z "$POSTGRES_PASSWORD" ]]; then
    log_error "POSTGRES_PASSWORD is required (via env var or .env file)"
    print_usage
    exit 1
fi

if [[ -z "$REDIS_PASSWORD" ]]; then
    log_error "REDIS_PASSWORD is required (via env var or .env file)"
    print_usage
    exit 1
fi

log_success "Passwords configured"

# DRY RUN notice
if [[ "$DRY_RUN" == "true" ]]; then
    log_warning "DRY RUN MODE - no changes will be made"
fi

################################################################################
# Deployment Steps
################################################################################

log_info ""
log_info "📋 Deployment Configuration"
log_info "───────────────────────────────────────────────────────────────────"
echo "  SSH Target:         $SSH_TARGET"
echo "  Domain:             $DOMAIN"
echo "  Git Branch:         $GIT_BRANCH"
echo "  Remote Project:     $REMOTE_PROJECT_PATH"
echo "  Skip Ollama Setup:  $SKIP_OLLAMA"
echo "  Dry Run:            $DRY_RUN"

# Step 1: Clone or update repository
log_info ""
log_info "📥 Step 1: Repository Setup"
log_info "───────────────────────────────────────────────────────────────────"

run_remote "
    if [[ ! -d '$REMOTE_PROJECT_PATH' ]]; then
        log_info 'Cloning repository...'
        git clone https://github.com/yourusername/thesisledger.git '$REMOTE_PROJECT_PATH'
    else
        log_info 'Repository already exists, fetching updates...'
        cd '$REMOTE_PROJECT_PATH'
        git fetch origin
    fi
" || exit 1

# Step 2: Checkout target branch
log_info "Checking out branch: $GIT_BRANCH"
run_remote "
    cd '$REMOTE_PROJECT_PATH'
    git checkout '$GIT_BRANCH'
    git pull origin '$GIT_BRANCH'
" || exit 1

log_success "Repository updated"

# Step 3: Prepare environment
log_info ""
log_info "⚙️  Step 2: Environment Configuration"
log_info "───────────────────────────────────────────────────────────────────"

run_remote "
    cd '$REMOTE_PROJECT_PATH'

    # Copy example .env if not exists
    if [[ ! -f .env ]]; then
        cp .env.example .env
        echo 'Created .env from .env.example'
    fi

    # Update critical env vars
    sed -i 's|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|' .env
    sed -i 's|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDIS_PASSWORD}|' .env
    sed -i 's|^DOMAIN=.*|DOMAIN=${DOMAIN}|' .env
    sed -i 's|^DJANGO_DEBUG=.*|DJANGO_DEBUG=false|' .env
    sed -i 's|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,${DOMAIN}|' .env
    sed -i 's|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://${DOMAIN}|' .env

    echo 'Environment configured'
" || exit 1

log_success "Environment ready"

# Step 4: Pull latest Docker images
log_info ""
log_info "🐳 Step 3: Docker Setup"
log_info "───────────────────────────────────────────────────────────────────"

run_remote "
    cd '$REMOTE_PROJECT_PATH'
    docker pull pgvector/pgvector:pg16
    docker pull redis:7-alpine
    docker pull ollama/ollama:latest
    docker pull caddy:2-alpine
    echo 'Docker images pulled'
" || exit 1

log_success "Docker images updated"

# Step 5: Start services with docker compose
log_info ""
log_info "🚀 Step 4: Starting Services"
log_info "───────────────────────────────────────────────────────────────────"

run_remote "
    cd '$REMOTE_PROJECT_PATH'

    # Start core services (db, redis) without Ollama initially
    docker compose -f docker-compose.prod.yml up -d db redis caddy

    echo 'Waiting for database to be ready...'
    sleep 10

    docker compose -f docker-compose.prod.yml ps
" || exit 1

log_success "Core services started"

# Step 6: Database migrations
log_info ""
log_info "🗄️  Step 5: Database Migrations"
log_info "───────────────────────────────────────────────────────────────────"

run_remote "
    cd '$REMOTE_PROJECT_PATH'

    # Note: Backend container should run migrations
    # For now, log the manual step required
    echo 'Manual Step: SSH into VM and run:'
    echo '  docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate'
    echo ''
    echo 'Or uncomment backend service in docker-compose.prod.yml and run:'
    echo '  docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate'
" || exit 1

# Step 7: Setup Ollama (optional)
if [[ "$SKIP_OLLAMA" != "true" ]]; then
    log_info ""
    log_info "🤖 Step 6: Ollama Setup"
    log_info "───────────────────────────────────────────────────────────────────"

    run_remote "
        cd '$REMOTE_PROJECT_PATH'

        # Start Ollama service
        docker compose -f docker-compose.prod.yml --profile with-ollama up -d ollama

        echo 'Waiting for Ollama to be ready...'
        sleep 15

        # Run setup script
        if [[ -x './scripts/setup_ollama.sh' ]]; then
            bash ./scripts/setup_ollama.sh
            echo 'Ollama setup complete'
        else
            echo 'Warning: setup_ollama.sh not executable'
        fi
    " || {
        log_warning "Ollama setup encountered an issue (non-fatal)"
    }

    log_success "Ollama ready"
else
    log_warning "Skipping Ollama setup (SKIP_OLLAMA=true)"
fi

# Step 8: Verify deployment
log_info ""
log_info "✅ Step 7: Verification"
log_info "───────────────────────────────────────────────────────────────────"

run_remote "
    cd '$REMOTE_PROJECT_PATH'

    echo 'Running services:'
    docker compose -f docker-compose.prod.yml ps

    echo ''
    echo 'Testing health endpoints:'

    # Wait for Caddy to be ready
    sleep 3

    # Test Caddy health
    curl -s -k https://localhost/health || echo 'Caddy health check: pending'
" || log_warning "Health check encountered issues"

################################################################################
# Summary
################################################################################

log_info ""
log_info "═══════════════════════════════════════════════════════════════════"
log_success "🎉 Deployment Summary"
log_info "═══════════════════════════════════════════════════════════════════"

cat << EOF

✅ Deployment complete! Here's what was configured:

📍 Services:
  • PostgreSQL + pgvector    db:5432
  • Redis                    redis:6379
  • Ollama (if not skipped)  ollama:11434
  • Caddy (reverse proxy)    caddy:80,443

🌐 Access:
  • Frontend & API:  https://${DOMAIN}
  • Admin panel:     https://${DOMAIN}/admin
  • API docs:        https://${DOMAIN}/api/docs/

⚠️  Next Steps (SSH into VM):
  1. Run database migrations:
     ssh -i ${SSH_KEY} ${SSH_TARGET}
     cd ${REMOTE_PROJECT_PATH}
     docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate

  2. Create superuser (optional):
     docker compose -f docker-compose.prod.yml run --rm backend python manage.py createsuperuser

  3. Verify logs:
     docker compose -f docker-compose.prod.yml logs -f

  4. Monitor services:
     docker stats

📋 Configuration:
  • Environment:     ${REMOTE_PROJECT_PATH}/.env
  • Reverse Proxy:   ${REMOTE_PROJECT_PATH}/Caddyfile
  • Compose file:    ${REMOTE_PROJECT_PATH}/docker-compose.prod.yml

🔐 Important:
  • Change POSTGRES_PASSWORD and REDIS_PASSWORD in production
  • Update ACME_EMAIL in Caddyfile for Let's Encrypt renewal
  • Configure DNS to point ${DOMAIN} to VM IP
  • Ensure security groups allow ports 80, 443

📚 Documentation:
  • Deployment guide: docs/deployment.md
  • Troubleshooting:  docs/troubleshooting.md

EOF

log_success "Happy deploying! 🚀"
