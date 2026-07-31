# Raw SEC Filings Data

This directory contains downloaded SEC 10-K and 10-Q filings organized by ticker symbol.

## Structure

```
raw/
├── AAPL/
│   ├── companyfacts_0000320193_2026-07-29T12:00:00.000000.json
│   ├── companyfacts_0000320193_2026-06-15T08:30:00.000000.json
│   └── ...
├── MSFT/
│   ├── companyfacts_0000789019_2026-07-28T14:22:00.000000.json
│   └── ...
└── [TICKER]/
    └── companyfacts_[CIK]_[TIMESTAMP].json
```

## File Format

Each file is downloaded from the SEC's XBRL API endpoint:
```
https://data.sec.gov/api/xbrl/companyfacts/CIK[###########].json
```

The JSON structure contains:
- Company metadata (CIK, entity name, stock symbol)
- Financial facts organized by taxonomy (us-gaap, ifrs-full, dei)
- Each fact includes values across multiple fiscal periods and amendments

## Tickers Covered

10 tickers across five sectors:

| Sector | Tickers |
|---|---|
| Technology | AAPL, MSFT, NVDA |
| Financials | JPM, V |
| Healthcare | UNH, LLY |
| Consumer | WMT, KO |
| Energy | XOM |

Scoped to 10 on purpose: embeddings are generated on CPU on the Oracle ARM box,
so the corpus needs to stay small enough to re-ingest in minutes rather than hours.

The same list is hardcoded in `scripts/download_filings.py` (`DEFAULT_TICKERS`) and
`backend/apps/ledger/management/commands/seed_companies.py` (`COMPANIES`). Changing
one without the other means `ingest_filings` silently skips that ticker.

## Current state (verified 2026-07-31)

**19 filings, 75 MB.** Two most recent 10-Ks per company (XOM and JPM have one
year each where only a single 10-K falls in the API's recent window).

| Ticker | Filings | Size | Ticker | Filings | Size |
|---|---|---|---|---|---|
| AAPL | 2 | 3.0M | UNH | 2 | 5.5M |
| MSFT | 2 | 16M | LLY | 2 | 5.4M |
| NVDA | 2 | 3.9M | WMT | 2 | 4.5M |
| JPM | 1 | 13M | KO | 2 | 7.4M |
| V | 2 | 5.6M | XOM | 2 | 12M |

Each filing is stored as `10k_{YEAR}.htm` (the primary document) plus a
`10k_{YEAR}.meta.json` recording accession number, period end, filing date and
source URL.

**Nothing here is committed to git.** 75 MB of HTML does not belong in the repo,
and the download is reproducible in about 20 seconds — just run the script.

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
