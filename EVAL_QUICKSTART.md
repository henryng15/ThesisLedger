# Evaluation Pipeline Quick Start

## Overview

The evaluation pipeline (`eval/runner.py`) measures RAG quality by:
1. Loading 20 realistic thesis-claim pairs from `eval/claims.json`
2. Searching pgvector for relevant filing chunks
3. Computing hit-rate and accuracy metrics
4. Outputting results in a clean terminal report

## Setup (One Time)

```bash
# 1. Ensure Django environment and migrations
cd backend
python manage.py migrate

# 2. Seed companies and filings
python manage.py seed_companies

# 3. Start Ollama (for embeddings)
docker compose --profile with-ollama up -d ollama
./scripts/setup_ollama.sh

# 4. Ingest filings and generate embeddings
# (This step lands on Day 6 per the project plan)
```

## Run Evaluation

```bash
cd eval
python runner.py
```

Output:
```
🚀 Starting RAG Evaluation (20 claims)

[01/20] ✓ AAPL   - sim=0.812 hit=100.0% | Services segment revenue growth exceeds...
[02/20] ✓ MSFT   - sim=0.745 hit=80.0%  | Capital expenditures for cloud and infra...
[03/20] ✓ GOOGL  - sim=0.691 hit=60.0%  | Revenue from non-advertising sources...
...

════════════════════════════════════════════════════════════════════════════════
ThesisLedger RAG Evaluation Results
════════════════════════════════════════════════════════════════════════════════

📊 Summary
────────────────────────────────────────────────────────────────────────────────
Total claims evaluated:     20
Successful retrievals:      18 (90.0%)
Failed retrievals:          2 (10.0%)

🎯 Retrieval Quality
────────────────────────────────────────────────────────────────────────────────
Average max similarity:     0.756
Average hit-rate (>0.5):    85.0%
Claims above threshold:     17/20 (85%)
Top-k for search:           5

📈 Coverage by Ticker
────────────────────────────────────────────────────────────────────────────────
✓ AAPL    1234 chunks  5 filings
✓ MSFT     892 chunks  4 filings
✓ GOOGL    567 chunks  3 filings
✗ V          0 chunks  0 filings
```

## Key Metrics Explained

| Metric | Meaning | Good Value |
|--------|---------|-----------|
| **Hit-Rate** | % of chunks with similarity > 0.5 | > 70% |
| **Avg Similarity** | Mean of best similarity scores | > 0.70 |
| **Coverage** | % of tickers with indexed chunks | 100% (if filings exist) |
| **Above Threshold** | % of claims with top result > 0.5 | > 80% |

## Evaluation Data

20 realistic claims covering major tickers:
- **Tech**: AAPL, MSFT, GOOGL, NVDA, META, NFLX, ORCL, UBER
- **Finance**: JPM, BAC
- **Healthcare**: UNH, JNJ
- **Consumer**: PG, KO, COST
- **Other**: TSLA, XOM, BA, V

Edit `eval/claims.json` to add custom evaluation pairs.

## Files

| File | Purpose |
|------|---------|
| `claims.json` | 20 thesis-claim pairs (ground truth) |
| `runner.py` | Main evaluation script |
| `README.md` | Detailed documentation |
| `__init__.py` | Python package marker |

## Common Issues

**No results / Failed retrievals:**
- Missing chunks? → Run filing ingestion (Day 6+)
- Ollama not running? → `docker compose --profile with-ollama up -d ollama`
- Embeddings not generated? → Filings need chunking + embedding step

**Low similarity scores:**
- Chunks too large/small? → Adjust chunking strategy
- Poor embedding model? → Try different model in `OLLAMA_EMBED_MODEL`
- Claims too different from filings? → Add more diverse claims to `claims.json`

## Integration with CI/CD

Run on each commit to detect RAG regressions:

```yaml
# .github/workflows/eval.yml
- name: RAG Evaluation
  run: |
    cd eval
    python runner.py > eval_results.txt
    # Compare against baseline
```

## Architecture

```
eval/runner.py
├── Load claims.json
├── For each claim:
│   ├── Generate embedding (Ollama)
│   ├── Search pgvector (cosine similarity)
│   ├── Calculate metrics
│   └── Store results
└── Format and print report
```

## Next Steps

- Integrate eval into your dev workflow
- Track metrics over time as chunking/embedding improves
- Adjust thresholds based on your use case
- Expand claims.json for broader coverage

See `eval/README.md` for complete documentation.
