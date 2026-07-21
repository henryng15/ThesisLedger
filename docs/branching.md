# Branching & PR conventions

Two developers, 14 days, one green `main`. Rules kept minimal on purpose.

## Branches

- `main` — always green. Protected by convention: no direct pushes, PR only.
- Work branches: `<type>/<day>-<short-slug>`, e.g. `feat/day3-thesis-api`, `fix/day7-graph-resume`.
- Types: `feat` · `fix` · `docs` · `test` · `chore` · `infra`.
- One branch per day-slice per developer. Delete after merge.

## Commits

Conventional Commits: `feat: persist thesis via POST /theses`.

- Imperative mood, lowercase subject, no trailing period.
- No AI co-author trailers, no "Generated with" lines.

## Pull requests

- Open early as draft; mark ready at the end-of-day sync.
- Reviewer is the other developer. Merge only after the EOD review.
- Squash merge, so `main` reads as one commit per slice.
- CI-less MVP: the author runs `pytest` (backend) / `npm run lint && npm run build` (frontend) and pastes the result into the PR checklist.

## Collision rule

The daily plan assigns different files to A and B. If a change must touch the other person's area, say so in the start-of-day sync and agree on the interface first — do not edit their files unilaterally.

Shared files that both may touch **only on Days 1–2**, then frozen: `docs/data_model.md`, `docs/api_contract.md`, `.env.example`.

## Tags

- `e2e-mock` — end of Day 4, full flow on mock data.
- `e2e-real` — end of Day 8, full flow on real filings + LLM.
- `v0.1.0` — Day 14 demo build.
