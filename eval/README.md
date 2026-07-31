# RAG Evaluation

Scores the real pipeline — pgvector retrieval plus LLM classification — against
hand-labelled verdicts. Nothing is simulated: every claim is embedded, retrieved
and classified exactly as a live analysis would do it.

## Files

- **`claims.json`** — 5 theses / 15 claims, one thesis per company in the corpus
- **`runner.py`** — the scorer
- **`README.md`** — this file

## The label set

15 claims, balanced across the three verdicts the system can emit:

| Verdict | Count | What it looks like |
|---|---|---|
| `supported` | 5 | Something the filing plainly states — "NVIDIA identifies Data Center as a reportable revenue category" |
| `contradicted` | 5 | Something the filing plainly refutes — "Visa issues credit cards directly to consumers" |
| `insufficient_evidence` | 5 | Something a 10-K would not address — forward-looking guidance, competitor internals, undisclosed geographic splits |

The balance matters. An earlier version of this set labelled every claim
`approve`, which meant a model answering "approve" unconditionally scored 100%.
Negative and unanswerable cases are what make the accuracy number mean anything.

## Prerequisites

```bash
# 1. Datastores and Ollama
docker compose --profile with-ollama up -d
docker exec thesisledger-ollama ollama pull nomic-embed-text
docker exec thesisledger-ollama ollama pull llama3.2:3b

# 2. Schema and companies
cd backend
python manage.py migrate
python manage.py seed_companies

# 3. Corpus — download, ingest, embed
SEC_USER_AGENT="ThesisLedger/0.1 (you@example.com)" python ../scripts/download_filings.py
python manage.py ingest_filings --data-dir ../data/raw
python -c "import django; django.setup(); from apps.ingestion.embeddings import embed_all_chunks; embed_all_chunks()"
```

Embedding is the slow step: roughly **35 chunks/min** on CPU, and it does not
parallelise — Ollama saturates on a single request. The 5-company corpus is 1330
chunks, so budget about 40 minutes.

## Running

```bash
python eval/runner.py                      # full set
python eval/runner.py --ticker AAPL        # one company
python eval/runner.py --limit 3            # first N claims
python eval/runner.py -k 3                 # retrieve 3 chunks instead of 5
python eval/runner.py --json results.json  # machine-readable output
```

## What is measured

**Classification accuracy** — predicted verdict against the label, plus
precision/recall/F1 per verdict so you can see *which* verdict the model gets
wrong. Confusing `contradicted` for `insufficient_evidence` is a very different
failure from the reverse.

**Retrieval quality** — hit rate, MRR and NDCG over the top-k chunks. Relevance
is graded by cosine similarity from pgvector against a 0.5 threshold. There is no
per-chunk human judgement, so this measures whether retrieval surfaced anything
usable and how highly it ranked — not human-judged topical relevance.

**Quote verification rate** — of the verdicts that are not
`insufficient_evidence`, the share carrying a quote found verbatim in its source
chunk. `classify_claim` downgrades a verdict when the quote cannot be verified,
so this should be 100%; anything less means the downgrade path has a hole.

**Latency** — mean and max seconds per claim. On CPU inference this dominates,
and it decides whether a live demo is viable.

## Results

See `docs-local/METRICS.md`.
