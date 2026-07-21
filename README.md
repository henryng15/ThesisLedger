# ThesisLedger

Turns an investment thesis into testable claims, then checks each claim against SEC
10-K/10-Q evidence via RAG. Every verdict cites a real passage — no fabricated citations.

Stack: Django REST + Celery/Redis · PostgreSQL + pgvector · LangChain + LangGraph ·
Ollama (local LLM/embeddings, provider fallback) · Next.js + TypeScript · Docker Compose · kind.

## How work lands

Two developers, one branch per day, one PR per branch. The branch name says who owns it:

```
devA/day1-foundations        Developer A
devB/day1-app-shell          Developer B
```

Day N branches off day N−1, so each PR shows only that day's diff. Merge in order.

Setup instructions arrive with the Day 1 branches.
