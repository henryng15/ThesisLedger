# ThesisLedger

Turns an investment thesis into testable claims, then checks each claim against SEC 10-K/10-Q evidence via RAG. Every verdict cites a real passage — no fabricated citations.

Stack: Django REST + Celery/Redis · PostgreSQL + pgvector · LangChain + LangGraph · Ollama (local LLM/embeddings, provider fallback) · Next.js + TypeScript · Docker Compose · kind.

Data model: [docs/data_model.md](docs/data_model.md) · Branching: [docs/branching.md](docs/branching.md)

## Quickstart (backend, Day 1 state)

Requires Docker and Python 3.12+.

```bash
cp .env.example .env                 # adjust POSTGRES_PORT if 5434 is taken
docker compose up -d                 # postgres+pgvector and redis
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Check it:

```bash
curl http://127.0.0.1:8000/api/health/
# {"status":"ok",...,"database":{"ok":true,"error":null,"pgvector":"0.8.5"}}
```

- API docs (Swagger): http://127.0.0.1:8000/api/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/
- Django admin: http://127.0.0.1:8000/admin/ (`manage.py createsuperuser` first)

Tests:

```bash
cd backend && .venv/bin/python -m pytest
```

## Layout

```
backend/            Django project (config/) + apps/ (core: health, pgvector extension)
infra/postgres/     first-boot SQL for the db container
docs/               data model, branching conventions
docker-compose.yml  db + redis (api, worker, frontend, ollama land on Day 10)
```
