# ThesisLedger — Architecture

## System overview

```mermaid
flowchart TB
    User([User])

    subgraph edge["Edge"]
        Caddy["Caddy<br/>auto HTTPS"]
    end

    subgraph app["Application"]
        FE["Next.js<br/>frontend"]
        API["Django REST<br/>api"]
        Worker["Celery<br/>worker"]
    end

    subgraph data["State"]
        PG[("PostgreSQL<br/>+ pgvector")]
        Redis[("Redis<br/>broker + cache")]
    end

    subgraph ai["Inference"]
        Ollama["Ollama<br/>llama3.2:3b<br/>nomic-embed-text"]
    end

    SEC[/"SEC EDGAR<br/>10-K filings"/]

    User --> Caddy
    Caddy --> FE
    Caddy --> API
    FE -->|"REST + polling"| API

    API --> PG
    API -->|"enqueue"| Redis
    API -->|"cache-aside"| Redis
    Redis -->|"consume"| Worker
    Worker --> PG
    Worker --> Ollama

    SEC -.->|"download_filings.py<br/>(offline)"| PG
```

## Analysis flow

What happens when a user submits a thesis.

```mermaid
sequenceDiagram
    participant U as User
    participant A as API
    participant R as Redis
    participant W as Worker
    participant O as Ollama
    participant P as Postgres

    U->>A: POST /theses
    A->>O: extract claims (LLM)
    O-->>A: ≤5 testable claims
    A->>P: persist thesis + claims
    A-->>U: claims for review

    U->>A: POST /claims/{id}/approve
    U->>A: POST /theses/{id}/analyze

    A->>R: check cache_key
    alt already analysed
        R-->>A: existing job_id
        A-->>U: 202 {cached: true}
    else new run
        A->>P: create AnalysisJob
        A->>R: enqueue task
        A-->>U: 202 {status: pending}

        R->>W: deliver task
        loop per approved claim
            W->>O: embed claim
            W->>P: pgvector top-k chunks
            W->>O: classify against chunks
            O-->>W: verdict + quote
            W->>P: write Evidence
        end
        W->>P: job status = done
    end

    loop until terminal
        U->>A: GET /jobs/{id}
        A->>P: read job + evidence
        A-->>U: progress / results
    end
```

## Ingestion (offline)

Runs once per corpus refresh, not per request.

```mermaid
flowchart LR
    A["download_filings.py"] -->|"10-K HTML"| B["data/raw/{TICKER}/"]
    B --> C["clean_filing_html<br/>strip tags"]
    C --> D["chunk_text<br/>1500 chars, 200 overlap"]
    D --> E["Chunk rows"]
    E --> F["embed_all_chunks<br/>nomic-embed-text"]
    F --> G[("pgvector<br/>768-dim")]
```

## Why these pieces

| Choice | Reason |
|---|---|
| **Celery + Redis** | Analysis takes minutes on CPU inference. A synchronous request would time out, so the API returns a job id and the frontend polls. |
| **pgvector, not a separate vector DB** | The corpus is ~6k chunks. A second datastore would be operational overhead for no gain, and evidence rows need to join to chunks anyway. |
| **Redis cache-aside** | The same thesis on the same company is deterministic. Re-running costs minutes of CPU, so the job id is cached and returned immediately. |
| **Ollama, self-hosted** | No API key or per-token cost, and the whole stack runs on one Always Free VM. `LLM_PROVIDER` allows swapping to Groq if CPU inference proves too slow. |
| **Quote verification** | A verdict other than `insufficient_evidence` must carry a quote found verbatim in its chunk. If the check fails the row is downgraded rather than emitting a fabricated citation. |

## Deployment

Single VM, Docker Compose. `kind` manifests in `k8s/` exist to demonstrate
horizontal worker scaling, not as the production target.

```mermaid
flowchart TB
    subgraph vm["Oracle Cloud — Ampere A1, 4 vCPU / 24GB"]
        direction TB
        C["caddy :80 :443"]
        F["frontend :3000"]
        A["api :8000"]
        W["worker"]
        D[("db :5432")]
        R[("redis :6379")]
        O["ollama :11434"]
        C --> F
        C --> A
        A --> D
        A --> R
        R --> W
        W --> D
        W --> O
    end
```
