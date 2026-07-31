#!/usr/bin/env bash
# Dump the ingested corpus — companies, filings, chunks and their embeddings —
# so it can be loaded into another database without re-running ingestion.
#
# Embedding is the expensive step (hours of CPU inference); the vectors are just
# rows once computed, so moving them is a 15MB file transfer, not a re-run.
#
#   ./scripts/export_corpus.sh                 # dump from the local compose db
#   ./scripts/export_corpus.sh out.sql         # custom output path
set -euo pipefail

OUT="${1:-corpus.sql}"
CONTAINER="${DB_CONTAINER:-thesisledger-db}"
DB="${POSTGRES_DB:-thesisledger}"
USER="${POSTGRES_USER:-thesisledger}"

TABLES="-t ledger_company -t ledger_filing -t ledger_chunk"

docker exec "$CONTAINER" pg_dump -U "$USER" -d "$DB" \
	--data-only --no-owner --no-privileges $TABLES > "$OUT"

rows=$(docker exec "$CONTAINER" psql -U "$USER" -d "$DB" -tAc \
	"SELECT count(*) FROM ledger_chunk WHERE embedding IS NOT NULL")

echo "Wrote $OUT ($(du -h "$OUT" | cut -f1)), $rows embedded chunks."
cat <<EOF

Load it into the target database (schema must already exist, so run
migrations first, and CREATE EXTENSION vector before that):

  psql "\$TARGET_URL" -v ON_ERROR_STOP=1 -f $OUT

Verify:

  psql "\$TARGET_URL" -c "SELECT count(*) FROM ledger_chunk WHERE embedding IS NOT NULL"
EOF
