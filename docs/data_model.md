# ThesisLedger — Data Model (v1, frozen after Day 2)

Owner: Developer A · Status: draft for Day 1 cross-review · Pairs with `docs/api_contract.md` (Developer B).

Seven tables. Ingestion side: `Company → Filing → Chunk`. Analysis side: `Thesis → Claim → Evidence`, driven by `AnalysisJob`.

```
Company 1─n Filing 1─n Chunk
   │                     ▲
   │                     │ (Evidence cites exactly one Chunk)
   └─1─n Thesis 1─n Claim 1─n Evidence
             │
             1─n AnalysisJob
```

---

## Conventions

- Primary keys: `UUID` (`uuid4`), so job payloads and URLs never leak row counts.
- Every table has `created_at` / `updated_at` (`auto_now_add` / `auto_now`, UTC).
- Enum-ish fields use `models.TextChoices` with `db_index=True` where filtered.
- Free text uses `TextField`; short labels use `CharField` with explicit `max_length`.
- Deletes cascade downward (deleting a `Thesis` removes its claims and evidence).

---

## 1. Company

The universe of supported issuers (3 for the MVP; tickers picked by Developer B).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `ticker` | CharField(10), unique | Uppercase, e.g. `AAPL` |
| `name` | CharField(255) | Display name in the selector |
| `cik` | CharField(10), unique | SEC Central Index Key, zero-padded |
| `is_active` | Boolean, default `True` | Hides a company from the selector without deleting filings |
| `created_at` / `updated_at` | DateTime | |

Indexes: `ticker` (unique), `cik` (unique).

## 2. Filing

One SEC document (10-K or 10-Q) belonging to a company.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `company` | FK → Company, `related_name="filings"`, CASCADE | |
| `filing_type` | Char(10), choices `10-K` / `10-Q` | Indexed |
| `period_end` | Date | Fiscal period the filing covers |
| `filed_at` | Date | Date filed with the SEC |
| `accession_number` | Char(25), unique | EDGAR accession, e.g. `0000320193-24-000123` |
| `source_url` | URLField(500) | Canonical EDGAR URL, shown as the citation link |
| `raw_text` | TextField | Cleaned plain text produced on Day 5 |
| `ingested_at` | DateTime, null | Set when chunking + embedding finished |
| `created_at` / `updated_at` | DateTime | |

Constraints: unique `accession_number`; unique together (`company`, `filing_type`, `period_end`).

## 3. Chunk

A retrievable passage of a filing, plus its embedding. This is the only table the vector search touches.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `filing` | FK → Filing, `related_name="chunks"`, CASCADE | |
| `ordinal` | Integer | Position within the filing, 0-based |
| `section` | Char(120) | Section-aware split label, e.g. `Item 7. MD&A` |
| `text` | TextField | The passage quoted back to the user |
| `char_start` / `char_end` | Integer | Offsets into `Filing.raw_text` for exact-quote verification |
| `token_count` | Integer | Sanity-check on chunk size |
| `embedding` | `VectorField(dimensions=EMBEDDING_DIM)` | pgvector; 768 for `nomic-embed-text` |
| `created_at` / `updated_at` | DateTime | |

Indexes:
- unique together (`filing`, `ordinal`)
- `HnswIndex(fields=["embedding"], m=16, ef_construction=64, opclasses=["vector_cosine_ops"])`
- B-tree on `section` for metadata-filtered retrieval

`search_chunks(company, query, k)` (Day 6) filters by `filing__company` first, then orders by cosine distance.

## 4. Thesis

The user's raw investment thesis for one company.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `company` | FK → Company, `related_name="theses"`, PROTECT | Never orphan a thesis by removing a company |
| `text` | TextField | Raw user input; validated non-empty, max ~5000 chars |
| `status` | Char(20), choices `draft` / `claims_generated` / `approved` / `analyzed` | Indexed |
| `created_at` / `updated_at` | DateTime | |

## 5. Claim

A testable statement extracted from the thesis. Hard cap: 5 per thesis (proposal §9).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `thesis` | FK → Thesis, `related_name="claims"`, CASCADE | |
| `ordinal` | Integer | Display order, 0-based |
| `text` | TextField | The claim as shown for edit/approve |
| `origin` | Char(10), choices `llm` / `user` | `user` once edited or manually added |
| `is_approved` | Boolean, default `False` | Set by the human-approval step |
| `created_at` / `updated_at` | DateTime | |

Constraints: unique together (`thesis`, `ordinal`); application-level guard rejects a 6th claim.

## 6. Evidence

The verdict for one claim, grounded in exactly one chunk. Written by the classification node.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `claim` | FK → Claim, `related_name="evidence"`, CASCADE | |
| `job` | FK → AnalysisJob, `related_name="evidence"`, CASCADE | Which run produced it |
| `status` | Char(24), choices `supported` / `contradicted` / `insufficient_evidence` | Indexed |
| `explanation` | TextField | One-paragraph rationale from the LLM |
| `quote` | TextField | Verbatim passage; must be a substring of `chunk.text` |
| `chunk` | FK → Chunk, null (null only for `insufficient_evidence`), PROTECT | The citation |
| `similarity` | Float, null | Retrieval score, for debugging and eval |
| `created_at` / `updated_at` | DateTime | |

Invariant enforced in code (Day 6 quote-verification): if `status != insufficient_evidence` then `chunk` is not null and `quote` occurs in `chunk.text`. A failed check downgrades the row to `insufficient_evidence` rather than emitting a fabricated citation.

Filing metadata shown in the UI (`filing_type`, `period_end`, `source_url`, `section`) is read through `evidence.chunk.filing` — never duplicated here.

## 7. AnalysisJob

One background run of the LangGraph workflow over a thesis's approved claims.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | Returned by `POST /theses/{id}/analyze`, polled via `GET /jobs/{id}` |
| `thesis` | FK → Thesis, `related_name="jobs"`, CASCADE | |
| `status` | Char(12), choices `pending` / `running` / `done` / `failed` | Indexed |
| `progress` | Integer, default 0 | Claims processed, for the progress indicator |
| `total_claims` | Integer, default 0 | Denominator of `progress` |
| `error` | TextField, blank | Structured error surfaced to the UI on `failed` |
| `graph_state` | JSONField, default dict | Serialized LangGraph state; survives pause/resume across the queue |
| `cache_key` | Char(64), blank, indexed | SHA-256 of (thesis text + company) for Redis cache-aside |
| `celery_task_id` | Char(64), blank | Set on Day 9 |
| `started_at` / `finished_at` | DateTime, null | |
| `created_at` / `updated_at` | DateTime | |

Status transitions: `pending → running → done`, or `→ failed` from either. Partial failures keep the job `done` and mark individual claims `insufficient_evidence`.

---

## Migration plan

| Migration | Day | Contents |
|---|---|---|
| `core/0001_enable_pgvector` | 1 | `CREATE EXTENSION vector` |
| `ledger/0001_initial` | 2 | All seven tables, without the HNSW index |
| `ledger/0002_chunk_embedding_index` | 6 | HNSW index, added after the first bulk embed |

Rationale: building the HNSW index before the rows exist is wasted work, and bulk inserts are faster without it.

## Open questions for cross-review (Day 1 EOD)

1. Ticker list — Developer B to confirm the 3 companies and how many filings each (proposal implies latest 10-K + recent 10-Qs).
2. Do we keep `Filing.raw_text` in Postgres, or on disk with only a path in the DB? Current call: in Postgres, simpler for a 2-week MVP.
3. Re-running analysis on the same thesis: new `AnalysisJob` row each time (keeps history) — confirmed against the API contract's job polling shape.
