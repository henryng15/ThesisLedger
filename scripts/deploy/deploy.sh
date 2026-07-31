#!/bin/bash
set -e

################################################################################
# ThesisLedger Production Deployment Script
#
# Deploys ThesisLedger infrastructure to a remote Ubuntu server (Oracle Cloud ARM VM recommended)
# - PostgreSQL + pgvector
# - Redis
# - Ollama (local LLM/embeddings)
# - Caddy (reverse proxy with automatic HTTPS)
#
# Usage:
#   export SSH_HOST=your-vm-ip
#   export DOMAIN=thesisledger.example.com
#   export POSTGRES_PASSWORD=$(openssl rand -base64 32)
#   export REDIS_PASSWORD=$(openssl rand -base64 32)
#   ./scripts/deploy/deploy.sh
#
# Environment Variables:
#   SSH_HOST             Target VM IP or hostname (required)
#   SSH_USER             SSH user (default: opc for Oracle Linux)
#   DOMAIN               Production domain (required)
#   POSTGRES_PASSWORD    PostgreSQL password (required)
#   REDIS_PASSWORD       Redis password (required)
#   SSH_KEY              Path to SSH private key (default: ~/.ssh/id_rsa)
################################################################################

set -u

SSH_HOST="${SSH_HOST:?Error: SSH_HOST not set}"
SSH_USER="${SSH_USER:-opc}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"
DOMAIN="${DOMAIN:?Error: DOMAIN not set}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?Error: POSTGRES_PASSWORD not set}"
REDIS_PASSWORD="${REDIS_PASSWORD:?Error: REDIS_PASSWORD not set}"

REMOTE_PATH="/home/${SSH_USER}/thesisledger"
SSH_TARGET="${SSH_USER}@${SSH_HOST}"

# Pre-flight checks
if [[ ! -f "$SSH_KEY" ]]; then
    echo "❌ SSH key not found: $SSH_KEY"
    exit 1
fi

echo "🔍 Testing SSH connection to $SSH_TARGET..."
ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$SSH_TARGET" "echo OK" > /dev/null || {
    echo "❌ Cannot connect to $SSH_TARGET"
    exit 1
}
echo "✅ SSH connection successful"

# Deploy
echo ""
echo "🚀 Deploying ThesisLedger to $SSH_TARGET"
echo "   Domain: $DOMAIN"
echo ""

ssh -i "$SSH_KEY" "$SSH_TARGET" bash <<REMOTE_SCRIPT
set -e

echo "📥 Pulling latest code from main..."
if [[ ! -d "$REMOTE_PATH" ]]; then
    git clone https://github.com/yourusername/thesisledger.git "$REMOTE_PATH" || true
fi

cd "$REMOTE_PATH"
git fetch origin main
git checkout main
git pull origin main

echo "✅ Code updated"
echo ""

echo "⚙️  Configuring environment..."
cp -n .env.example .env || true

# Update .env with production settings
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" .env
sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASSWORD|" .env
sed -i "s|^DOMAIN=.*|DOMAIN=$DOMAIN|" .env
sed -i "s|^DJANGO_DEBUG=.*|DJANGO_DEBUG=false|" .env
sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,$DOMAIN|" .env
sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://$DOMAIN|" .env

echo "✅ Environment configured"
echo ""

echo "🐳 Starting Docker services..."
docker compose -f docker-compose.prod.yml up -d --build

echo "⏳ Waiting for database..."
sleep 10

docker compose -f docker-compose.prod.yml ps
echo ""

echo "🤖 Setting up Ollama..."
docker compose -f docker-compose.prod.yml --profile with-ollama up -d ollama
sleep 15

bash ./scripts/setup_ollama.sh --host localhost --port 11434 --wait 120 || {
    echo "⚠️  Ollama setup failed (non-fatal)"
}
echo ""

echo "🗄️  Running database migrations..."
if docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate 2>/dev/null; then
    echo "✅ Migrations applied"
else
    echo "⚠️  Backend service not available in compose file yet"
    echo "   To run migrations later, uncomment the backend service in docker-compose.prod.yml"
    echo "   Then run: docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "  1. Seed initial data:"
echo "     docker compose -f docker-compose.prod.yml run --rm backend python manage.py seed_companies"
echo ""
echo "  2. Create superuser:"
echo "     docker compose -f docker-compose.prod.yml run --rm backend python manage.py createsuperuser"
echo ""
echo "  3. View logs:"
echo "     docker compose -f docker-compose.prod.yml logs -f"
echo ""
echo "  4. Access:"
echo "     https://$DOMAIN               (Frontend)"
echo "     https://$DOMAIN/api/docs      (API documentation)"
echo "     https://$DOMAIN/admin         (Django admin)"

REMOTE_SCRIPT

echo ""
echo "🎉 Deployment successful!"
