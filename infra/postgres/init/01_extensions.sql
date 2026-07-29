-- Runs once on first container start (empty data volume).
-- Django migration core/0001 also enables it, so a fresh clone works either way.
CREATE EXTENSION IF NOT EXISTS vector;
