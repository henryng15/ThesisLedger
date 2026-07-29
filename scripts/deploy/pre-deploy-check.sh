#!/bin/bash
set -euo pipefail

################################################################################
# Pre-Deployment Checklist
#
# Validates configuration before running main deployment script
#
# Usage:
#   ./scripts/deploy/pre-deploy-check.sh
################################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

check_count=0
pass_count=0
fail_count=0

log_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

log_pass() {
    echo -e "${GREEN}✓ ${1}${NC}"
    ((pass_count++))
}

log_fail() {
    echo -e "${RED}✗ ${1}${NC}"
    ((fail_count++))
}

log_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

check() {
    ((check_count++))
}

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}ThesisLedger Pre-Deployment Checklist${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo ""

# 1. Check environment variables
echo -e "${BLUE}1. Environment Variables${NC}"
echo "───────────────────────────────────────────────────────────────────"

check
if [[ -n "${SSH_HOST:-}" ]]; then
    log_pass "SSH_HOST is set: $SSH_HOST"
else
    log_fail "SSH_HOST is not set"
fi

check
if [[ -n "${DOMAIN:-}" ]]; then
    log_pass "DOMAIN is set: $DOMAIN"
else
    log_fail "DOMAIN is not set"
fi

check
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    log_pass "POSTGRES_PASSWORD is set (length: ${#POSTGRES_PASSWORD})"
else
    log_fail "POSTGRES_PASSWORD is not set"
fi

check
if [[ -n "${REDIS_PASSWORD:-}" ]]; then
    log_pass "REDIS_PASSWORD is set (length: ${#REDIS_PASSWORD})"
else
    log_fail "REDIS_PASSWORD is not set"
fi

check
SSH_USER="${SSH_USER:-opc}"
if [[ -n "$SSH_USER" ]]; then
    log_pass "SSH_USER is set: $SSH_USER"
else
    log_fail "SSH_USER is not set"
fi

# 2. Check local files and scripts
echo ""
echo -e "${BLUE}2. Local Files & Scripts${NC}"
echo "───────────────────────────────────────────────────────────────────"

check
if [[ -f "docker-compose.yml" ]]; then
    log_pass "docker-compose.yml exists"
else
    log_fail "docker-compose.yml not found"
fi

check
if [[ -f "docker-compose.prod.yml" ]]; then
    log_pass "docker-compose.prod.yml exists"
else
    log_fail "docker-compose.prod.yml not found"
fi

check
if [[ -f "Caddyfile" ]]; then
    log_pass "Caddyfile exists"
else
    log_fail "Caddyfile not found"
fi

check
if [[ -f ".env.example" ]]; then
    log_pass ".env.example exists"
else
    log_fail ".env.example not found"
fi

check
if [[ -f ".env.prod.example" ]]; then
    log_pass ".env.prod.example exists"
else
    log_fail ".env.prod.example not found"
fi

check
if [[ -f "scripts/deploy/deploy.sh" ]]; then
    log_pass "scripts/deploy/deploy.sh exists"
    if [[ -x "scripts/deploy/deploy.sh" ]]; then
        log_pass "  → deploy.sh is executable"
    else
        log_warning "  → deploy.sh is not executable (will chmod +x on deploy)"
    fi
else
    log_fail "scripts/deploy/deploy.sh not found"
fi

check
if [[ -f "scripts/setup_ollama.sh" ]]; then
    log_pass "scripts/setup_ollama.sh exists"
else
    log_fail "scripts/setup_ollama.sh not found"
fi

# 3. Check SSH configuration
echo ""
echo -e "${BLUE}3. SSH Configuration${NC}"
echo "───────────────────────────────────────────────────────────────────"

SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"

check
if [[ -f "$SSH_KEY" ]]; then
    log_pass "SSH key exists: $SSH_KEY"
else
    log_fail "SSH key not found: $SSH_KEY"
fi

check
if [[ -n "${SSH_HOST:-}" ]]; then
    if timeout 5 ssh -i "$SSH_KEY" -o ConnectTimeout=3 "${SSH_USER:-opc}@${SSH_HOST}" "echo 'Connection OK'" > /dev/null 2>&1; then
        log_pass "SSH connection to ${SSH_USER:-opc}@${SSH_HOST} successful"
    else
        log_fail "Cannot SSH to ${SSH_USER:-opc}@${SSH_HOST}"
        log_info "  Troubleshooting:"
        log_info "    - Verify SSH_HOST is correct"
        log_info "    - Verify SSH_USER is correct (default: opc)"
        log_info "    - Verify SSH key has correct permissions (600)"
        log_info "    - Verify Oracle Cloud security group allows port 22"
    fi
fi

# 4. Check local dependencies
echo ""
echo -e "${BLUE}4. Local Dependencies${NC}"
echo "───────────────────────────────────────────────────────────────────"

check
if command -v ssh &> /dev/null; then
    log_pass "ssh is installed"
else
    log_fail "ssh is not installed"
fi

check
if command -v git &> /dev/null; then
    log_pass "git is installed ($(git --version))"
else
    log_fail "git is not installed"
fi

check
if command -v openssl &> /dev/null; then
    log_pass "openssl is installed"
else
    log_fail "openssl is not installed"
fi

# 5. Check domain configuration
echo ""
echo -e "${BLUE}5. Domain & DNS Configuration${NC}"
echo "───────────────────────────────────────────────────────────────────"

check
if [[ -n "${DOMAIN:-}" ]]; then
    if dig +short "$DOMAIN" | grep -q .; then
        log_pass "DNS for $DOMAIN is configured"
    else
        log_warning "No DNS A record found for $DOMAIN (may not be propagated yet)"
    fi
else
    log_fail "DOMAIN not set, cannot check DNS"
fi

# 6. Check password strength
echo ""
echo -e "${BLUE}6. Password Configuration${NC}"
echo "───────────────────────────────────────────────────────────────────"

check
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    if [[ ${#POSTGRES_PASSWORD} -ge 16 ]]; then
        log_pass "POSTGRES_PASSWORD is reasonably strong (${#POSTGRES_PASSWORD} chars)"
    else
        log_warning "POSTGRES_PASSWORD is short (${#POSTGRES_PASSWORD} chars, recommend ≥16)"
    fi
fi

check
if [[ -n "${REDIS_PASSWORD:-}" ]]; then
    if [[ ${#REDIS_PASSWORD} -ge 16 ]]; then
        log_pass "REDIS_PASSWORD is reasonably strong (${#REDIS_PASSWORD} chars)"
    else
        log_warning "REDIS_PASSWORD is short (${#REDIS_PASSWORD} chars, recommend ≥16)"
    fi
fi

# Summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo "Checks run:    $check_count"
echo -e "${GREEN}Passed:        $pass_count${NC}"
if [[ $fail_count -gt 0 ]]; then
    echo -e "${RED}Failed:        $fail_count${NC}"
else
    echo -e "${GREEN}Failed:        $fail_count${NC}"
fi

echo ""

if [[ $fail_count -eq 0 ]]; then
    echo -e "${GREEN}✓ All checks passed! Ready to deploy.${NC}"
    echo ""
    echo "Next step:"
    echo "  ./scripts/deploy/deploy.sh"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please fix the issues above and try again.${NC}"
    echo ""
    echo "Common fixes:"
    echo "  1. Set required env vars:"
    echo "     export SSH_HOST=your-vm.example.com"
    echo "     export DOMAIN=your-domain.example.com"
    echo "     export POSTGRES_PASSWORD=\$(openssl rand -base64 32)"
    echo "     export REDIS_PASSWORD=\$(openssl rand -base64 32)"
    echo ""
    echo "  2. Check SSH configuration:"
    echo "     chmod 600 ~/.ssh/id_rsa"
    echo "     ssh -i ~/.ssh/id_rsa opc@your-vm.example.com"
    echo ""
    echo "  3. Verify domain DNS:"
    echo "     dig your-domain.example.com"
    echo ""
    exit 1
fi
