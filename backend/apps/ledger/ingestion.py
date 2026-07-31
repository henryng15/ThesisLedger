"""Simple filing ingestion helpers for Day 6."""

from __future__ import annotations

import re
from typing import Any

from django.utils import timezone

from apps.ledger.models import Chunk, Company, Filing


class IngestionServiceError(RuntimeError):
    """Raised when filing text cannot be chunked into retrievable passages."""


def chunk_text(text: str, *, chunk_size: int = 1200) -> list[str]:
    """Split raw filing text into chunks with a deterministic paragraph-aware splitter."""
    if not text.strip():
        return []

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        if current and (current_length + len(paragraph) > chunk_size or len(current) >= 2):
            chunks.append("\n\n".join(current))
            current = []
            current_length = 0

        current.append(paragraph)
        current_length += len(paragraph)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def ingest_filing(company: Company, *, filing_type: str, period_end: str, filed_at: str, accession_number: str, source_url: str, raw_text: str) -> Filing:
    """Create a filing and chunk rows from a raw filing body."""
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

    chunk_texts = chunk_text(raw_text)
    Chunk.objects.bulk_create(
        [
            Chunk(
                filing=filing,
                ordinal=index,
                section="document",
                text=chunk_text,
                char_start=0,
                char_end=len(chunk_text),
                token_count=max(1, len(chunk_text.split())),
            )
            for index, chunk_text in enumerate(chunk_texts)
        ]
    )
    return filing
