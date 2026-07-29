# RAG Evaluation Pipeline

Evaluates the Retrieval-Augmented Generation pipeline by measuring how well the vector search retrieves relevant chunks from SEC filings for investment thesis claims.

## Files

- **`claims.json`** — 20 realistic thesis-to-claim evaluation pairs covering major tickers (AAPL, MSFT, JPM, UNH, TSLA, etc.)
- **`runner.py`** — Evaluation script that measures retrieval hit-rate and classification accuracy
- **`README.md`** — This file

## Running Evaluation

### Prerequisites

1. Django environment set up with migrations applied:
   ```bash
   cd backend
   python manage.py migrate
   ```

2. Companies and filings in the database (seeded or manually added):
   ```bash
   python manage.py seed_companies
   ```

3. Chunks with embeddings indexed in pgvector:
   ```bash
   # If using Ollama, ensure it's running
   docker compose --profile with-ollama up -d ollama
   ```

### Run Full Evaluation

```bash
cd eval
python runner.py
```

Or with custom options:

```bash
python runner.py --eval-data claims.json --top-k 5
```

### Options

- `--eval-data PATH` — Path to evaluation claims JSON (default: `eval/claims.json`)
- `--top-k K` — Number of chunks to retrieve per claim (default: 5)

## What Gets Measured

### Retrieval Hit-Rate

Percentage of claims for which the vector search returned relevant chunks.

- **Hit** = chunk with similarity score > 0.5
- Metric: `(claims_with_hits / total_claims) × 100`

### Classification Accuracy

- **Coverage** — % of tickers with indexed chunks available for search
- **Average Similarity** — Mean of max similarity scores across all claims
- **Claims Above Threshold** — % of claims where best result scored > 0.5

### Per-Ticker Metrics

- Chunk count per ticker
- Filing count per ticker
- Coverage status (✓ = chunks available, ✗ = no chunks)

## Output Format

```
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
✓ JPM      456 chunks  2 filings
✗ V          0 chunks  0 filings

📋 Detailed Results (Top Findings)
────────────────────────────────────────────────────────────────────────────────

1. AAPL - Services segment revenue growth exceeds Products segment growth...
   ✓ Retrieved: similarity=0.812
     Section: Item 1. Business
     Filing: 10-Q (2024-01-31)

2. MSFT - Capital expenditures for cloud and infrastructure have increased...
   ✓ Retrieved: similarity=0.745
     Section: Item 7. Management's Discussion and Analysis
     Filing: 10-K (2023-12-31)
```

## Evaluation Pairs Structure

Each claim in `claims.json` has:

```json
{
  "thesis": "Short user-facing investment thesis",
  "expected_claim": "Specific testable claim from the thesis",
  "target_ticker": "Company ticker (e.g., AAPL)"
}
```

The thesis is background context; the script evaluates retrieval for the `expected_claim`.

## Similarity Thresholds

The evaluation uses a **0.5 similarity threshold** (on a 0–1 scale from cosine similarity):

- `similarity > 0.8` — Excellent match, very likely relevant
- `0.6 < similarity ≤ 0.8` — Good match, probably relevant
- `0.5 < similarity ≤ 0.6` — Fair match, possibly relevant
- `similarity ≤ 0.5` — Poor match, likely not relevant

Adjust the threshold in `runner.py` by modifying:
```python
if r.get("similarity", 0) > 0.5:  # Change 0.5 to your threshold
```

## Troubleshooting

### No results returned

1. Check if filings exist:
   ```bash
   cd backend
   python manage.py shell
   >>> from apps.ledger.models import Filing
   >>> Filing.objects.count()
   ```

2. Check if chunks are created:
   ```bash
   >>> from apps.ledger.models import Chunk
   >>> Chunk.objects.count()
   ```

3. Check if embeddings are populated:
   ```bash
   >>> Chunk.objects.filter(embedding__isnull=False).count()
   ```

### Embedding service errors

- Ensure Ollama is running:
  ```bash
  curl http://localhost:11434/api/tags
  ```

- Check `OLLAMA_BASE_URL` and `OLLAMA_EMBED_MODEL` in `.env`

### Database connection errors

- Verify PostgreSQL is running:
  ```bash
  docker ps | grep thesisledger-db
  ```

- Check connection settings in `.env`

## Development

### Adding Custom Evaluation Pairs

Edit `claims.json` and add new pairs following the same structure:

```json
{
  "thesis": "Your investment thesis here",
  "expected_claim": "A specific, testable claim",
  "target_ticker": "TICKER"
}
```

### Modifying Metrics

Edit the `RAGEvaluator` class in `runner.py`:

- **`calculate_hit_rate()`** — Change relevance threshold
- **`search_chunks()`** — Modify ranking/filtering logic
- **`format_output()`** — Change output formatting

## Performance Notes

- Evaluation runs in ~30 seconds for 20 claims (depending on chunk count)
- Vector search uses pgvector's HNSW index if present (see `docs/data_model.md`)
- Embedding generation via Ollama takes ~100-200ms per claim

## Next Steps

- Run evaluation on each dev iteration to track RAG quality
- Adjust chunk size/overlap to improve hit-rate
- Use results to refine embedding model selection
- Integrate into CI/CD for regression detection

