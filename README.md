# ThesisLedger

Turns an investment thesis into testable claims, then checks each claim against SEC 10-K/10-Q evidence via RAG. Every verdict cites a real passage — no fabricated citations.

Stack: Django REST + Celery/Redis · PostgreSQL + pgvector · LangChain + LangGraph · Ollama (local LLM/embeddings, provider fallback) · Next.js + TypeScript · Docker Compose · kind.

Data model: [docs/data_model.md](docs/data_model.md) · API contract: [docs/api_contract.md](docs/api_contract.md) · Branching: [docs/branching.md](docs/branching.md)

## Quickstart (backend)

Requires Docker and Python 3.12+.

```bash
cp .env.example .env                 # adjust POSTGRES_PORT if 5434 is taken
docker compose up -d                 # postgres+pgvector and redis
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_companies   # AAPL, MSFT, NVDA
.venv/bin/python manage.py runserver
```

Check it:

```bash
curl http://127.0.0.1:8000/api/health/
# {"status":"ok",...,"database":{"ok":true,"error":null,"pgvector":"0.8.5"}}
curl http://127.0.0.1:8000/api/companies/
```

- API docs (Swagger): http://127.0.0.1:8000/api/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/
- Django admin: http://127.0.0.1:8000/admin/ (`manage.py createsuperuser` first)

Tests:

```bash
cd backend && .venv/bin/python -m pytest
```

## Day 5 status

The backend now has a provider-backed claim generation seam and an embedding adapter that can target Ollama locally. The flow is:

- claim extraction uses the LLM adapter in [backend/apps/ledger/llm_service.py](backend/apps/ledger/llm_service.py)
- the claim generator falls back to deterministic demo claims if Ollama is unavailable in [backend/apps/ledger/claim_generation.py](backend/apps/ledger/claim_generation.py)
- embedding requests are routed through [backend/apps/ledger/embeddings.py](backend/apps/ledger/embeddings.py)

Set these env vars before running locally:

```bash
cp .env.example .env
# then adjust:
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_LLM_MODEL=llama3.2:3b
# OLLAMA_EMBED_MODEL=nomic-embed-text
# LLM_PROVIDER=ollama
```

## API status

Thesis and claim endpoints are backed by the database. The analysis job lifecycle is
still a fixture until Day 4. Shapes come from [docs/api_contract.md](docs/api_contract.md)
and `apps/ledger/tests.py` asserts them, so swapping a stub cannot drift the contract.

| Endpoint | State |
|---|---|
| `GET /api/health/` | real |
| `GET /api/companies/` | real (seeded) |
| `POST /api/theses/` | real |
| `GET /api/theses/{id}/` | real |
| `POST /api/theses/{id}/claims:generate` | real persistence, claim text still mocked (LLM on Day 7) |
| `PATCH` / `DELETE /api/claims/{id}/` | real |
| `POST /api/theses/{id}/claims:approve` | real |
| `POST /api/theses/{id}/analyze` | validates approvals, returns a fixture job id |
| `GET /api/jobs/{id}/` | fixture |

## Production Deployment

Deploy ThesisLedger infrastructure (PostgreSQL, Redis, Ollama, Caddy reverse proxy) to a remote Ubuntu server (Oracle Cloud ARM VM recommended).

### Quick Start

1. **Prepare credentials** (run locally):
   ```bash
   export SSH_HOST=your-vm-ip
   export DOMAIN=thesisledger.example.com
   export SSH_USER=opc  # default for Oracle Linux
   export POSTGRES_PASSWORD=$(openssl rand -base64 32)
   export REDIS_PASSWORD=$(openssl rand -base64 32)
   ```

2. **Deploy**:
   ```bash
   ./scripts/deploy/deploy.sh
   ```

   This will:
   - Pull latest code from `main` branch
   - Start PostgreSQL + pgvector, Redis, Ollama, and Caddy
   - Configure environment variables and DNS
   - Set up Ollama with `llama3.2:3b` (LLM) and `nomic-embed-text` (embeddings)
   - Run Django database migrations

3. **Post-deployment** (SSH into the VM):
   ```bash
   ssh -i ~/.ssh/id_rsa opc@your-vm-ip
   cd ~/thesisledger
   
   # Seed initial data
   docker compose -f docker-compose.prod.yml run --rm backend python manage.py seed_companies
   
   # Create superuser for Django admin
   docker compose -f docker-compose.prod.yml run --rm backend python manage.py createsuperuser
   ```

4. **Verify**:
   ```bash
   curl https://thesisledger.example.com/api/health/
   # Should return: {"status":"ok","database":{"ok":true,...}}
   ```

### Deployed Services

| Service | Port | Notes |
|---------|------|-------|
| Caddy (reverse proxy) | 80, 443 | Automatic HTTPS via Let's Encrypt |
| PostgreSQL + pgvector | 5432 (internal) | Persistent volume: `pgdata_prod` |
| Redis | 6379 (internal) | Persistent append-only file |
| Ollama | 11434 (internal) | Models in `ollama_models_prod` volume |
| Backend API | via Caddy | Django at `https://thesisledger.example.com/api` |
| Frontend | via Caddy | Next.js at `https://thesisledger.example.com` |

### Configuration

All configuration is handled automatically by `deploy.sh`. To customize after deployment, SSH into the VM and edit:

- `.env` — Environment variables (passwords, domain, ports)
- `Caddyfile` — Reverse proxy routing rules
- `docker-compose.prod.yml` — Service definitions

### Troubleshooting

**Cannot SSH to VM:**
```bash
chmod 600 ~/.ssh/id_rsa
ssh -i ~/.ssh/id_rsa opc@your-vm-ip
# If still failing, check Oracle Cloud security group allows port 22
```

**Ollama model pull fails:**
```bash
ssh -i ~/.ssh/id_rsa opc@your-vm-ip
cd ~/thesisledger
docker compose -f docker-compose.prod.yml --profile with-ollama logs ollama
bash scripts/setup_ollama.sh --wait 300
```

**Database migration fails:**
```bash
ssh -i ~/.ssh/id_rsa opc@your-vm-ip
cd ~/thesisledger
docker compose -f docker-compose.prod.yml logs db
docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate --verbosity 3
```

**Services not responding:**
```bash
ssh -i ~/.ssh/id_rsa opc@your-vm-ip
cd ~/thesisledger
docker compose -f docker-compose.prod.yml ps         # Check service status
docker compose -f docker-compose.prod.yml logs       # View logs
docker compose -f docker-compose.prod.yml logs -f    # Follow logs in real-time
```

## Layout

```
backend/            Django project (config/) + apps/ (core: health · ledger: models, API)
infra/postgres/     first-boot SQL for the db container
docs/               data model, API contract, branching conventions
docker-compose.yml  db + redis (api, worker, frontend, ollama land on Day 10)
scripts/
  deploy/           Deployment automation
    deploy.sh       Main deployment script (run this)
    pre-deploy-check.sh  Validation checklist
  setup_ollama.sh   Ollama model initialization
Caddyfile           Reverse proxy configuration (HTTP/HTTPS routing)
```
