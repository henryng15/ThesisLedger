# Branching & PR conventions

Three developers (A · B · C), one green `main`. Rules kept minimal on purpose.  
Sprint plan (internal): `docs-local/SPRINT_2DAY_3DEVS.md` (file ownership map).

## Branches

- `main` — always green. Protected by convention: no direct pushes, PR only.
- Work branches: `<type>/<day>-<short-slug>`, e.g. `feat/day1-analysis-job`, `feat/day2-ingest-filings`.
- Prefix with owner when helpful: `feat/A-day1-jobs`, `feat/B-day1-raw-filings`, `feat/C-day1-generate-claims`.
- Types: `feat` · `fix` · `docs` · `test` · `chore` · `infra`.
- One branch per day-slice per developer. Delete after merge.

## Commits

Conventional Commits: `feat: persist thesis via POST /theses`.

- Imperative mood, lowercase subject, no trailing period.
- No AI co-author trailers, no "Generated with" lines.

## Pull requests

- Open early as draft; mark ready at the end-of-day sync.
- Reviewer: another developer (rotate). Merge only after the EOD review.
- Squash merge, so `main` reads as one commit per slice.
- CI-less MVP: the author runs `pytest` (backend) / `npm run lint && npm run build` (frontend) and pastes the result into the PR checklist.

## Collision rule

The sprint plan assigns disjoint trees to A, B, and C. If a change must touch another person's area, say so in the start-of-day sync and agree on the interface first — do not edit their files unilaterally.

Frozen unless all three agree: `docs/data_model.md`, `docs/api_contract.md`.

## Tags

- `e2e-mock` — full mock flow on real `AnalysisJob` rows (target: end of this 2-day sprint).
- `e2e-real` — full flow on real filings + LLM (later).
- `v0.1.0` — final demo build.
