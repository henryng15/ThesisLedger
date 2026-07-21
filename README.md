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

## Layout

```
backend/            Django project (config/) + apps/ (core: health · ledger: models, API)
infra/postgres/     first-boot SQL for the db container
docs/               data model, API contract, branching conventions
docker-compose.yml  db + redis (api, worker, frontend, ollama land on Day 10)
```
