# ThesisLedger Production Deployment

Deployment scripts and configuration for Oracle Cloud ARM (Ampere A1) VM.

## Quick Start

### 1. Prerequisites

- SSH access to Oracle Cloud VM (4 vCPU, 24GB RAM)
- Docker and Docker Compose installed on VM
- Git installed on VM
- Domain name (for HTTPS via Let's Encrypt)
- SSH key for passwordless authentication

### 2. Environment Setup

Create a `.env.prod` file in the project root (based on `.env.example`):

```bash
# Copy template
cp .env.example .env.prod

# Generate secure passwords
POSTGRES_PASSWORD=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)

# Export for deployment script
export SSH_HOST=your-oracle-vm.example.com
export SSH_USER=opc  # Default for Oracle Linux
export DOMAIN=thesisledger.example.com
export POSTGRES_PASSWORD=$POSTGRES_PASSWORD
export REDIS_PASSWORD=$REDIS_PASSWORD
export GIT_BRANCH=main
```

### 3. Execute Deployment

```bash
# From project root
./scripts/deploy/deploy.sh
```

Or with custom options:

```bash
# Dry run (print commands without executing)
DRY_RUN=true ./scripts/deploy/deploy.sh

# Skip Ollama setup
SKIP_OLLAMA=true ./scripts/deploy/deploy.sh
```

## Deployment Scripts

### `deploy.sh`

Main deployment orchestrator:
- Connects to Oracle VM via SSH
- Clones/updates repository
- Configures environment variables
- Pulls Docker images
- Starts services (db, redis, ollama, caddy)
- Runs setup scripts

**Features:**
- `set -e` for error handling
- Color-coded output
- Progress logging
- Dry-run mode
- Pre-flight checks (SSH, keys, passwords)

**Requirements:**
- `SSH_HOST` — Target VM hostname/IP
- `DOMAIN` — Production domain
- `POSTGRES_PASSWORD` — Database password
- `REDIS_PASSWORD` — Redis password

## Configuration Files

### `docker-compose.prod.yml`

Production Docker Compose configuration:

**Services:**
- **Caddy** — Reverse proxy with automatic HTTPS (Let's Encrypt)
- **PostgreSQL** — pgvector for embedding storage
- **Redis** — Celery broker + cache
- **Ollama** — Local LLM/embedding (optional, behind `with-ollama` profile)

**Key Differences from Dev:**
- JSON logging (for log aggregation)
- Restart policies (`unless-stopped`)
- Volume naming with `_prod` suffix
- Passwords required (not defaults)
- Network isolation (`thesisledger-net`)

### `Caddyfile`

Reverse proxy configuration:

**Routes:**
- `/api/*` → Django backend (port 8000)
- `/static/*` → Static files from backend
- `/admin*` → Django admin panel
- `/` → Next.js frontend (port 3000)

**Features:**
- Automatic HTTPS (Let's Encrypt)
- Header forwarding (Host, X-Forwarded-*, etc.)
- WebSocket support
- gzip compression
- JSON logging

## Deployment Architecture

```
Internet
   ↓ (HTTPS)
┌──────────────────────────────────────┐
│ Caddy Reverse Proxy                  │
│ (Port 80, 443)                       │
└──────────────┬───────────────────────┘
               ├─ /api/* → Backend (8000)
               └─ / → Frontend (3000)
                      ↓
            ┌─────────────────┐
            │ Docker Network  │
            │                 │
            ├─ PostgreSQL     │
            ├─ Redis          │
            ├─ Ollama (opt)   │
            └─ Containers     │
```

## Post-Deployment Steps

### 1. SSH into VM

```bash
ssh -i ~/.ssh/id_rsa opc@your-oracle-vm.example.com
cd /home/opc/thesisledger
```

### 2. Run Database Migrations

```bash
docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate
```

### 3. Create Superuser (Optional)

```bash
docker compose -f docker-compose.prod.yml run --rm backend python manage.py createsuperuser
```

### 4. Verify Services

```bash
# Check running containers
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f caddy
docker compose -f docker-compose.prod.yml logs -f db
docker compose -f docker-compose.prod.yml logs -f redis
docker compose -f docker-compose.prod.yml logs -f ollama

# Test endpoints
curl -k https://thesisledger.example.com/health
curl -k https://thesisledger.example.com/api/health/
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SSH_HOST` | VM hostname/IP | `oracle-prod.example.com` |
| `DOMAIN` | Production domain | `thesisledger.example.com` |
| `POSTGRES_PASSWORD` | Database password | `$(openssl rand -base64 32)` |
| `REDIS_PASSWORD` | Redis password | `$(openssl rand -base64 32)` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `SSH_USER` | SSH username | `opc` |
| `SSH_KEY` | Path to SSH key | `~/.ssh/id_rsa` |
| `GIT_BRANCH` | Branch to deploy | `main` |
| `SKIP_OLLAMA` | Skip Ollama setup | `false` |
| `DRY_RUN` | Print without executing | `false` |

## Troubleshooting

### SSH Connection Fails

```bash
# Verify SSH key
ssh-keygen -y -f ~/.ssh/id_rsa

# Test connection with verbose output
ssh -i ~/.ssh/id_rsa -vvv opc@oracle-vm.example.com

# Ensure VM security group allows SSH (port 22)
```

### Docker Services Don't Start

```bash
# SSH into VM
ssh opc@oracle-vm.example.com

# Check Docker logs
docker compose -f docker-compose.prod.yml logs

# Verify Docker is running
docker ps

# Restart Docker daemon
sudo systemctl restart docker
```

### Database Connection Fails

```bash
# Check if database is running
docker compose -f docker-compose.prod.yml ps db

# View PostgreSQL logs
docker compose -f docker-compose.prod.yml logs db

# Test connection from container
docker compose -f docker-compose.prod.yml run --rm db psql -h db -U thesisledger -d thesisledger -c "SELECT 1"
```

### Ollama Models Not Pulling

```bash
# Verify Ollama container is running
docker compose -f docker-compose.prod.yml ps ollama

# Check Ollama logs
docker compose -f docker-compose.prod.yml logs ollama

# Manual model pull
docker compose -f docker-compose.prod.yml exec ollama ollama pull llama3.2:3b
docker compose -f docker-compose.prod.yml exec ollama ollama pull nomic-embed-text
```

### HTTPS Certificate Not Renewing

```bash
# Check Caddy logs
docker compose -f docker-compose.prod.yml logs caddy

# Check certificate expiration
docker compose -f docker-compose.prod.yml exec caddy caddy version

# Reload Caddy config
docker compose -f docker-compose.prod.yml reload caddy
```

## Monitoring & Maintenance

### Check Resource Usage

```bash
# Real-time stats
docker stats

# Specific container
docker stats thesisledger-db

# System info
free -h
df -h
```

### Backup Database

```bash
# Dump PostgreSQL
docker compose -f docker-compose.prod.yml exec db pg_dump -U thesisledger thesisledger > backup_$(date +%Y%m%d).sql

# With compression
docker compose -f docker-compose.prod.yml exec db pg_dump -U thesisledger thesisledger | gzip > backup_$(date +%Y%m%d).sql.gz
```

### View Service Logs

```bash
# Tail all logs
docker compose -f docker-compose.prod.yml logs -f

# Tail specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f caddy

# View last N lines
docker compose -f docker-compose.prod.yml logs --tail=100 db
```

## Security Checklist

- [ ] Change default `POSTGRES_PASSWORD` and `REDIS_PASSWORD`
- [ ] Update `ACME_EMAIL` in Caddyfile for Let's Encrypt
- [ ] Configure Oracle Cloud security groups:
  - [ ] Allow port 80 (HTTP)
  - [ ] Allow port 443 (HTTPS)
  - [ ] Allow port 22 (SSH, restrict to your IP)
- [ ] Disable SSH password login (use keys only)
- [ ] Set `DJANGO_DEBUG=false` in `.env`
- [ ] Configure `ALLOWED_HOSTS` for your domain
- [ ] Enable regular database backups
- [ ] Monitor disk space (Ollama models are large)
- [ ] Set up log rotation

## Performance Tuning

### For 4 vCPU, 24GB RAM:

```env
# Ollama
OLLAMA_NUM_PARALLEL=1
OLLAMA_NUM_GPU=0  # CPU-only on ARM

# PostgreSQL (shared_buffers ~1/4 of RAM)
POSTGRES_SHARED_BUFFERS=6GB
POSTGRES_EFFECTIVE_CACHE_SIZE=18GB

# Redis (maxmemory limit)
REDIS_MAXMEMORY=4gb
```

## Rollback

To rollback to previous version:

```bash
# SSH into VM
ssh opc@oracle-vm.example.com
cd /home/opc/thesisledger

# Checkout previous commit
git checkout main~1

# Restart services
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## Support

- Check logs: `docker compose -f docker-compose.prod.yml logs -f`
- SSH to VM and debug manually
- Refer to individual service documentation (Django, Next.js, Ollama, etc.)

