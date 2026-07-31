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

50 major tickers across sectors:
- **Tech**: AAPL, MSFT, GOOGL, AMZN, NVDA, META, NFLX, ORCL, IBM, INTC
- **Finance**: JPM, BAC, WFC, GS, MS
- **Healthcare**: UNH, JNJ, PFE, AZN, LLY
- **Consumer**: PG, KO, MCD, NKE, HD, COST, WMT, TGT, AZO
- **Energy**: XOM, CVX, SLB, MPC, COP
- **Aerospace**: BA, LMT, RTX, GD, NOC
- **Automotive**: TSLA, F, GM, LCID, RIVN
- **Growth**: UBER, LYFT, DASH, SPOT, PINS

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
