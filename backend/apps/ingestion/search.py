"""Chunk retrieval with pgvector similarity search.

Provides search_chunks() for finding relevant filing passages
given a query string. Uses cosine similarity over embeddings.
"""

import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from apps.ledger.models import Chunk

logger = logging.getLogger(__name__)


def search_chunks(
    company_id: str,
    query: str,
    k: int = 5,
) -> list["Chunk"]:
    """Find the top-k most relevant chunks for a query.

    Day 1 stub: Returns first k chunks for the company.
    Day 2: Uses real pgvector similarity search.

    Args:
        company_id: UUID of the company to search within
        query: Text to find similar chunks for
        k: Number of chunks to return

    Returns:
        List of Chunk objects ordered by relevance
    """
    from apps.ledger.models import Chunk

    # Stub implementation: return first k chunks for company
    # Real implementation will use embeddings (see search_chunks_real below)
    chunks = list(
        Chunk.objects
        .filter(filing__company_id=company_id)
        .select_related("filing")
        .order_by("filing__period_end", "ordinal")[:k]
    )

    if not chunks:
        logger.warning(f"No chunks found for company {company_id}")

    return chunks


def search_chunks_real(
    company_id: str,
    query: str,
    k: int = 5,
) -> list["Chunk"]:
    """Real vector similarity search using pgvector.

    Requires embeddings to be populated. Falls back to stub if
    query embedding fails.

    Args:
        company_id: UUID of the company to search within
        query: Text to find similar chunks for
        k: Number of chunks to return

    Returns:
        List of Chunk objects with distance annotations
    """
    from pgvector.django import CosineDistance

    from apps.ingestion.embeddings import get_embedding
    from apps.ledger.models import Chunk

    try:
        query_embedding = get_embedding(query)
    except Exception as e:
        logger.warning(f"Failed to get query embedding: {e}, falling back to stub")
        return search_chunks(company_id, query, k)

    chunks = list(
        Chunk.objects
        .filter(filing__company_id=company_id)
        .exclude(embedding__isnull=True)
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .select_related("filing")
        .order_by("distance")[:k]
    )

    logger.debug(f"Found {len(chunks)} chunks for query (first distance: {chunks[0].distance if chunks else 'N/A'})")
    return chunks
