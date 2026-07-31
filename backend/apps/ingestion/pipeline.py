"""Programmatic filing ingestion.

The management command drives ingestion from files on disk; this module holds
the part that is useful on its own — turning already-extracted filing text into
a `Filing` plus its `Chunk` rows — so tests and scripts can call it directly.
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.ingestion.chunker import chunk_text
from apps.ledger.models import Chunk, Company, Filing


class IngestionError(RuntimeError):
    """Raised when filing text cannot be chunked into retrievable passages."""


@transaction.atomic
def ingest_filing(
    company: Company,
    *,
    filing_type: str,
    period_end: date,
    filed_at: date,
    accession_number: str,
    source_url: str,
    raw_text: str,
) -> Filing:
    """Persist a filing and its chunks. Returns the created Filing.

    Raises IngestionError when the text yields no usable chunks, so a filing row
    is never left behind with nothing retrievable attached to it.
    """
    if not raw_text.strip():
        raise IngestionError(f"Empty filing text for {company.ticker} {accession_number}")

    # chunk_text yields a single chunk for short input rather than nothing, so
    # drop blank ones here instead of relying on an empty iterator.
    chunks = [info for info in chunk_text(raw_text) if info.text.strip()]
    if not chunks:
        raise IngestionError(f"No chunks produced for {company.ticker} {accession_number}")

    filing = Filing.objects.create(
        company=company,
        filing_type=filing_type,
        period_end=period_end,
        filed_at=filed_at,
        accession_number=accession_number,
        source_url=source_url,
        raw_text=raw_text,
        ingested_at=timezone.now(),
    )

    Chunk.objects.bulk_create(
        Chunk(
            filing=filing,
            ordinal=info.ordinal,
            section=info.section,
            text=info.text,
            char_start=info.char_start,
            char_end=info.char_end,
            token_count=len(info.text) // 4,
        )
        for info in chunks
    )

    return filing
