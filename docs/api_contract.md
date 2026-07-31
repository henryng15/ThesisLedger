# ThesisLedger — API Contract (v1 draft)

Base URL: `/api`. JSON in, JSON out. All ids are UUID strings. Timestamps are ISO-8601 UTC.

Status: **draft written by Developer A on Day 2 so the stub endpoints have something to match.** Developer B owns this file — review, adjust, then freeze at Day 2 EOD. The stubs in `apps/ledger/views.py` and the tests in `apps/ledger/tests.py` are generated from these shapes, so a change here means a change there.

Live schema once the server runs: `/api/schema/` (OpenAPI) and `/api/docs/` (Swagger).

---

## Enumerations

| Enum | Values |
|---|---|
| `thesis.status` | `draft` · `claims_generated` · `approved` · `analyzed` |
| `claim.origin` | `llm` · `user` |
| `evidence.status` | `supported` · `contradicted` · `insufficient_evidence` |
| `job.status` | `pending` · `running` · `done` · `failed` |
| `filing.filing_type` | `10-K` · `10-Q` |

## Error shape

Every 4xx/5xx returns the same envelope:

```json
{ "error": { "code": "validation_error", "message": "Thesis text must not be empty.", "field": "text" } }
```

Codes: `validation_error` (400) · `not_found` (404) · `conflict` (409) · `llm_error` (502) · `internal_error` (500).

---

## 1. `GET /api/health/`

Liveness plus dependency check. Used by Docker healthchecks and kind probes.

```json
{
  "status": "ok",
  "service": "thesisledger-api",
  "version": "0.1.0",
  "database": { "ok": true, "error": null, "pgvector": "0.8.5" }
}
```

`503` with `"status": "degraded"` if the DB is unreachable or pgvector is missing.

## 2. `GET /api/companies/`

Supported issuers for the selector. Real data from the DB (seeded via `manage.py seed_companies`).

```json
{
  "results": [
    { "id": "…", "ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193", "filing_count": 0 }
  ]
}
```

## 3. `POST /api/theses/`

Create a thesis.

Request:

```json
{ "company_id": "…", "text": "Apple's services segment will keep growing faster than hardware." }
```

Rules: `text` non-empty, ≤ 5000 chars; `company_id` must exist and be active.

Response `201`:

```json
{
  "id": "…",
  "company": { "id": "…", "ticker": "AAPL", "name": "Apple Inc." },
  "text": "…",
  "status": "draft",
  "claims": [],
  "created_at": "2026-07-21T20:00:00Z"
}
```

## 4. `GET /api/theses/{id}/`

Same shape as above, with `claims` populated once generated.

## 5. `POST /api/theses/{id}/claims:generate`

Extract up to 5 claims. **Asynchronous** — extraction is an LLM call that takes
minutes on CPU inference, far longer than an HTTP request can wait, so the work
is queued and the response returns immediately.

Request body: none (or `{"force": true}` to regenerate and replace existing
claims — the old ones are deleted, so their ids change).

Response `202`:

```json
{ "thesis_id": "…", "status": "draft", "claims": [] }
```

`claims` is empty and `status` is still `draft` in the normal case: the worker
has the job but has not finished. **Poll `GET /api/theses/{id}/`** until
`status` becomes `claims_generated`, then read `claims` from that response.

If the broker is unreachable the API falls back to extracting inline, in which
case the response already carries `status: "claims_generated"` and the claims.
Either way, polling the thesis is the correct client behaviour.

Errors: `409 conflict` if claims exist and `force` is not set.

## 6. `PATCH /api/claims/{id}/`

Edit one claim. Body: `{ "text": "…" }`. Editing flips `origin` to `user`. Returns the claim object.

## 7. `DELETE /api/claims/{id}/`

Removes a claim. `204`, no body.

## 8. `POST /api/theses/{id}/claims:approve`

Freeze the claim set the analysis will run on.

Request: `{ "claim_ids": ["…", "…"] }` — the claims to mark approved (others are left unapproved).

Response `200`:

```json
{ "thesis_id": "…", "status": "approved", "approved_claim_ids": ["…"] }
```

Errors: `400 validation_error` if the list is empty or contains ids from another thesis.

## 9. `POST /api/theses/{id}/analyze`

Start an analysis run over the approved claims. Returns immediately.

Response `202`:

```json
{ "job_id": "…", "status": "pending", "thesis_id": "…", "total_claims": 3 }
```

`status` reflects the job's actual state at response time. It is `pending` in the
normal case (queued for a Celery worker), but if the broker is unreachable the
analysis runs inline and the job may already be `running` or `done`. Clients
should poll `GET /api/jobs/{id}` until a terminal state either way.

A repeat request for an unchanged thesis is deduplicated: the response carries an
extra `"cached": true` and reuses the existing `job_id`.

Errors: `400 validation_error` if no approved claims.

## 10. `GET /api/jobs/{id}/`

Polled by the frontend every ~2s until `done` or `failed`.

```json
{
  "id": "…",
  "thesis_id": "…",
  "status": "done",
  "progress": 3,
  "total_claims": 3,
  "error": null,
  "started_at": "2026-07-21T20:00:01Z",
  "finished_at": "2026-07-21T20:00:09Z",
  "results": [
    {
      "claim": { "id": "…", "ordinal": 0, "text": "…" },
      "evidence": {
        "id": "…",
        "status": "supported",
        "explanation": "The filing reports services revenue up 14% year over year versus 2% for products.",
        "quote": "Services net sales increased 14% during 2024 compared to 2023.",
        "similarity": 0.83,
        "source": {
          "chunk_id": "…",
          "section": "Item 7. Management's Discussion and Analysis",
          "filing_type": "10-K",
          "period_end": "2024-09-28",
          "filed_at": "2024-11-01",
          "source_url": "https://www.sec.gov/Archives/edgar/data/320193/…"
        }
      }
    }
  ]
}
```

Rules:
- `results` is `[]` while `pending` / `running`; partial results may appear during `running` once the graph writes them (Day 9).
- `evidence.source` is `null` only when `status` is `insufficient_evidence`. Every other status carries a real chunk — no fabricated citations.
- `quote` is always a verbatim substring of the cited chunk's text.

---

## Frontend polling contract

1. `POST /theses/` → thesis id
2. `POST /theses/{id}/claims:generate` → render claims for edit
3. `PATCH` / `DELETE` per claim as the user edits
4. `POST /theses/{id}/claims:approve` → approved set
5. `POST /theses/{id}/analyze` → job id
6. `GET /jobs/{id}/` every 2s, stop on `done` / `failed`, render `results`

## Open questions for Developer B

1. Does the UI need `GET /theses/` (history list), or is a single thesis per session enough for the MVP?
2. Should `claims:approve` also accept edited text in one call, or is `PATCH` per claim enough?
3. Pagination on `companies` — 3 rows in the MVP, so `results` without a cursor. Confirm.
