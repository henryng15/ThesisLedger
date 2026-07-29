## What

<!-- One or two lines. Which day-slice of the two-week plan does this close? -->

Day: <!-- e.g. Day 3 -->  ·  Developer: <!-- A / B -->

## Why

<!-- Link the plan item or the Definition-of-Done row (proposal §9) this advances. -->

## How to verify

```bash
# commands the reviewer can paste
```

## Checklist

- [ ] Tests run locally and pass (`pytest` / `npm run lint && npm run build`)
- [ ] No change to a frozen contract (`docs/data_model.md`, `docs/api_contract.md`) — or the other developer approved it
- [ ] Migrations included and reversible, if models changed
- [ ] `.env.example` updated, if new config was introduced
- [ ] No secrets, no `.env`, no large binaries committed
