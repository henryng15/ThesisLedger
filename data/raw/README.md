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

## Downloading Filings

Run the download script from the project root:

```bash
python scripts/download_filings.py

# Or specify custom tickers:
python scripts/download_filings.py --tickers AAPL MSFT GOOGL

# Or set a custom output directory:
python scripts/download_filings.py --output-dir /path/to/data
```

Set the SEC User-Agent in `.env` or via CLI:
```bash
SEC_USER_AGENT="YourOrg/1.0 (your.email@example.com)" python scripts/download_filings.py
```

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
