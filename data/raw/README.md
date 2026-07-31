# Raw SEC Filings Data

10-K filings downloaded from SEC EDGAR, one directory per ticker.

## Structure

```
raw/
├── AAPL/
│   ├── 10k_2024.htm         # primary document, as filed
│   └── 10k_2024.meta.json   # accession number, dates, source URL
├── MSFT/
│   ├── 10k_2025.htm
│   └── 10k_2025.meta.json
└── [TICKER]/
```

The `.htm` file is the filing itself — the narrative text the RAG pipeline reads.
`apps.ingestion` globs `*.htm*`, strips the markup, and chunks the result.

> Earlier revisions of the downloader fetched XBRL `companyfacts` JSON instead.
> That endpoint returns numeric financial facts, not filing prose, so none of it
> was usable for retrieval.

## Current state (verified 2026-07-31)

**5 filings, 20 MB, 1330 chunks.** Most recent 10-K per company.

| Ticker | Company | Sector | Chunks |
|---|---|---|---|
| AAPL | Apple | Technology | 160 |
| MSFT | Microsoft | Technology | 249 |
| NVDA | NVIDIA | Technology | 262 |
| V | Visa | Financials | 332 |
| XOM | Exxon Mobil | Energy | 327 |

Scoped to 5 companies / 1 filing each for the demo. Embedding is CPU-bound
through Ollama at roughly 35 chunks/min, so this corpus indexes in about 40
minutes; the earlier 10-company two-year corpus would have taken 3.5 hours.

Each filing is stored as `10k_{YEAR}.htm` plus a `10k_{YEAR}.meta.json`
recording accession number, period end, filing date and source URL.

**Nothing here is committed to git.** The download is reproducible in seconds —
just run the script.

## Downloading Filings

Run the download script from the project root:

```bash
# SEC rejects requests whose User-Agent has no contact email, so this is required.
SEC_USER_AGENT="ThesisLedger/0.1 (you@example.com)" python scripts/download_filings.py

# More years per company:
... --per-ticker 4

# Different companies (falls back to SEC's live ticker→CIK map):
... --tickers AAPL MSFT GOOGL
```

Re-running is safe: files already on disk are skipped, so this is an incremental
top-up rather than a full re-download.

## Rate Limiting

The script respects SEC's rate-limiting policy:
- Minimum 0.1 seconds between requests
- Default delay: 0.5 seconds
- 3 retries on transient failures
- Timeout: 30 seconds per request

## Data Processing Pipeline

1. **Extraction** → Parse JSON filings, extract claim-relevant facts
2. **Embedding** → Generate embeddings via Ollama (nomic-embed-text)
3. **Storage** → Index into PostgreSQL (pgvector) via RAG backend
4. **Querying** → Semantic search to support claim verification

See [docs/data_model.md](../docs/data_model.md) for the database schema.
