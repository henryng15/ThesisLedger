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

## API status

`companies` reads the database. Every other endpoint returns hard-coded JSON matching
[docs/api_contract.md](docs/api_contract.md) until real persistence lands (Days 3–4);
`apps/ledger/tests.py` asserts those shapes so the swap cannot drift.

| Endpoint | State |
|---|---|
| `GET /api/health/` | real |
| `GET /api/companies/` | real (seeded) |
| `POST /api/theses/` | stub, validation real |
| `GET /api/theses/{id}/` | stub |
| `POST /api/theses/{id}/claims:generate` | stub |
| `PATCH` / `DELETE /api/claims/{id}/` | stub |
| `POST /api/theses/{id}/claims:approve` | stub |
| `POST /api/theses/{id}/analyze` | stub |
| `GET /api/jobs/{id}/` | stub |

## Layout

```
backend/            Django project (config/) + apps/ (core: health · ledger: models, API)
infra/postgres/     first-boot SQL for the db container
docs/               data model, API contract, branching conventions
docker-compose.yml  db + redis (api, worker, frontend, ollama land on Day 10)
```
