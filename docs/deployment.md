# Deployment

Five pieces, four providers. Deploy in this order — each step needs values
produced by the one before it.

```
Vercel (Next.js)  ──▶  Railway (Django API + Celery worker)
                             │
                  ┌──────────┼──────────┐
                  ▼          ▼          ▼
             Supabase     Upstash    Oracle VM
             (pgvector)   (Redis)    (Ollama)
```

| Piece | Provider | Why |
|---|---|---|
| Frontend | Vercel | Native Next.js target |
| API + worker | Railway | Runs `backend/Dockerfile` twice with different commands |
| Postgres + pgvector | Supabase | pgvector available on the free tier |
| Redis | Upstash | Managed, but see the Celery caveat below |
| Ollama | Oracle VM | No per-token cost; needs a whole machine |

---

## 1. Supabase — database

1. Create a project. Save the database password.
2. SQL Editor → run:

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. Settings → Database → copy **both** connection strings. You need both:
   - **Direct** (port `5432`) — for migrations
   - **Pooler / transaction mode** (port `6543`) — for the running app

**Why both.** The pooler is pgbouncer in transaction mode. It multiplexes
statements across connections, so anything that keeps server-side state between
statements breaks — server-side cursors, and `CREATE INDEX CONCURRENTLY` during
migrations. Run migrations against the direct connection, serve traffic through
the pooler, and set `DISABLE_SERVER_SIDE_CURSORS=true`.

---

## 2. Upstash — Redis

Create a database, copy the `rediss://` URL (TLS, note the double `s`).

**Read this before relying on the free tier.** Celery is not a typical cache
client. Each idle worker runs a blocking `BRPOP` that re-issues on a timeout, so
workers consume commands continuously whether or not any work exists. Upstash
bills per command, and the free tier is 10k/day — an idle worker can exhaust
that on its own.

`CELERY_BROKER_TRANSPORT_OPTIONS` already sets a 30s socket timeout and a 5s
polling interval, which cuts idle command volume substantially — a queued job
still starts within ~5 seconds. Raise `CELERY_POLLING_INTERVAL` further if you
are still hitting the cap.

Beyond that, the simplest lever is to stop the worker when you are not demoing.
An idle worker is the only thing consuming commands when nobody is using the
app.

---

## 3. Oracle VM — Ollama

The config lives in `deploy/oracle/`. Ollama has **no authentication of its
own**, so it must never be exposed directly: anyone who finds port 11434 can run
inference on your box, and `/api/delete` would let them wipe your models. Caddy
fronts it with TLS, a bearer token, and an endpoint allowlist. Ollama itself
binds to loopback.

```bash
ssh -i your-key.key ubuntu@<VM_IP>
git clone https://github.com/henryng15/thesisledger.git
cd thesisledger/deploy/oracle

cp .env.example .env
# DOMAIN      — a domain pointing at this IP, or <IP>.sslip.io
# ACME_EMAIL  — any address you own
# OLLAMA_TOKEN— openssl rand -hex 32
nano .env

docker compose up -d
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull nomic-embed-text
```

### Open ports 80 and 443 — both layers

Oracle blocks in two independent places.

**Console:** Networking → Virtual Cloud Networks → your VCN → Subnets → your
subnet → Security Lists → Add Ingress Rules. Source `0.0.0.0/0`, TCP, ports 80
and 443.

**In the VM — order matters.** Ubuntu images ship with a catch-all REJECT.
Appending with `-A` puts your rule *after* it, where it never runs:

```
4  ACCEPT  tcp dpt:22
5  REJECT  all           ← evaluation stops here
6  ACCEPT  tcp dpt:80    ← dead rule
```

Insert *before* the REJECT instead, then persist:

```bash
sudo iptables -I INPUT 5 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 5 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -L INPUT -n --line-numbers | head -10   # ACCEPTs must precede REJECT
sudo netfilter-persistent save
```

Verify from somewhere else — TLS should answer, and an unauthenticated call
should be refused:

```bash
curl https://<DOMAIN>/health                    # OK
curl https://<DOMAIN>/api/tags                  # Unauthorized
curl -H "Authorization: Bearer <TOKEN>" https://<DOMAIN>/api/tags   # model list
```

---

## 4. Railway — API and worker

Two services from the same repo, both building `backend/Dockerfile`.

**Service `api`** — start command:

```
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

**Service `worker`** — start command:

```
celery -A config worker -l info -c 1
```

Concurrency 1 on purpose: every task calls Ollama, and Ollama serialises anyway.

### Environment (both services)

```bash
DJANGO_SECRET_KEY=<openssl rand -hex 32>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<api>.up.railway.app
TRUST_PROXY_SSL_HEADER=true

# Supabase — pooler for traffic
POSTGRES_HOST=aws-0-<region>.pooler.supabase.com
POSTGRES_PORT=6543
POSTGRES_DB=postgres
POSTGRES_USER=postgres.<project-ref>
POSTGRES_PASSWORD=<password>
POSTGRES_SSLMODE=require
DISABLE_SERVER_SIDE_CURSORS=true

REDIS_URL=rediss://default:<token>@<host>.upstash.io:6379

OLLAMA_URL=https://<DOMAIN>
OLLAMA_TOKEN=<same token as the VM>
OLLAMA_MODEL=llama3.2:3b
OLLAMA_EMBED_MODEL=nomic-embed-text
USE_REAL_ANALYSIS=true

CORS_ALLOWED_ORIGINS=https://<app>.vercel.app
CSRF_TRUSTED_ORIGINS=https://<app>.vercel.app
```

### Migrate

Schema only — the data comes from the corpus dump in step 6, so do **not** run
`seed_companies` here. Run against the **direct** Supabase connection (port
5432), not the pooler; pgbouncer in transaction mode cannot run every migration
statement.

```bash
railway run --service api python manage.py migrate
```

---

## 5. Vercel — frontend

Root directory `frontend/`. Vercel detects Next.js; the Dockerfile is not used.

```
NEXT_PUBLIC_API_BASE_URL=https://<api>.up.railway.app/api
```

This is baked in at build time, so changing it needs a redeploy. After the first
deploy, put the Vercel URL into Railway's `CORS_ALLOWED_ORIGINS` and
`CSRF_TRUSTED_ORIGINS` and redeploy the API.

---

## 6. Load the corpus

The corpus is **already ingested and embedded** in the local development
database. Embedding is the expensive part — hours of CPU inference — but the
vectors are ordinary rows once computed, so moving them is a 15 MB file copy,
not a re-run.

```bash
# 1. Schema first, against the DIRECT Supabase connection (port 5432)
cd backend
POSTGRES_HOST=<direct-host> POSTGRES_PORT=5432 \
POSTGRES_DB=postgres POSTGRES_USER=postgres.<ref> \
POSTGRES_PASSWORD=<pw> POSTGRES_SSLMODE=require \
  python manage.py migrate

# 2. Dump locally
cd ..
./scripts/export_corpus.sh corpus.sql

# 3. Load
psql "postgresql://postgres.<ref>:<pw>@<direct-host>:5432/postgres?sslmode=require" \
  -v ON_ERROR_STOP=1 -f corpus.sql
```

Verify:

```bash
psql "$TARGET_URL" -c \
  "SELECT count(*) FILTER (WHERE embedding IS NOT NULL) AS embedded, count(*) FROM ledger_chunk"
```

Expect **1330 of 1330**. Do not run `seed_companies` afterwards — the dump
already carries the company rows, and re-seeding would conflict on ticker.

### If you ever do need to re-ingest from scratch

Only necessary when changing the corpus, the chunker, or the embedding model:

```bash
SEC_USER_AGENT="ThesisLedger/0.1 (you@example.com)" python scripts/download_filings.py
python manage.py ingest_filings --data-dir ../data/raw
python -c "import django; django.setup(); from apps.ingestion.embeddings import embed_all_chunks; embed_all_chunks()"
```

Measured at ~26 chunks/min on a 16-core machine — about 50 minutes for 1330
chunks. Against the 2-core Oracle box over the internet it is materially
slower, so run it under `nohup` or `tmux`. This is exactly why the dump exists.

## Smoke test

```bash
curl https://<api>.up.railway.app/api/health/
curl https://<api>.up.railway.app/api/companies/
curl -H "Authorization: Bearer <TOKEN>" https://<DOMAIN>/api/tags
```

Then the full flow in the browser: pick a company, submit a thesis, approve
claims, run the analysis. First run is slow; a repeat of the same thesis returns
instantly from the Redis cache.

---

## Cost and limits

| Provider | Free tier | Watch for |
|---|---|---|
| Vercel | Generous for hobby | — |
| Railway | ~$5 credit/month | Two always-on services burn it; sleep the worker when idle |
| Supabase | 500 MB | Corpus vectors are ~50 MB; fine. Projects pause after inactivity |
| Upstash | 10k commands/day | **Celery polling can exhaust this on its own** |
| Oracle | Always Free | A1 ARM often out of capacity; x86 shapes are smaller |
