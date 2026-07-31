"""Embedding generation using Ollama.

Generates vector embeddings for text using the nomic-embed-text model
running on Ollama. Embeddings are stored in pgvector for similarity search.
"""

import logging
from typing import Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# Connection timeout for Ollama
TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def get_embedding(text: str, model: Optional[str] = None) -> list[float]:
    """Get embedding vector for text using Ollama.

    Args:
        text: Text to embed
        model: Model name (defaults to settings.OLLAMA_EMBED_MODEL)

    Returns:
        List of floats representing the embedding

    Raises:
        httpx.HTTPError: On connection or API errors
        ValueError: On invalid response
    """
    model = model or settings.OLLAMA_EMBED_MODEL
    url = f"{settings.OLLAMA_URL}/api/embeddings"

    response = httpx.post(
        url,
        json={"model": model, "prompt": text},
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    data = response.json()
    embedding = data.get("embedding")

    if not embedding or not isinstance(embedding, list):
        raise ValueError(f"Invalid embedding response: {data}")

    return embedding


def embed_chunks_batch(texts: list[str], model: Optional[str] = None) -> list[list[float]]:
    """Get embeddings for multiple texts.

    Processes texts one at a time (Ollama doesn't support batching).
    Logs progress for long batches.

    Args:
        texts: List of texts to embed
        model: Model name (defaults to settings.OLLAMA_EMBED_MODEL)

    Returns:
        List of embedding vectors
    """
    embeddings = []
    total = len(texts)

    for i, text in enumerate(texts):
        if i > 0 and i % 50 == 0:
            logger.info(f"Embedded {i}/{total} chunks")

        try:
            embedding = get_embedding(text, model)
            embeddings.append(embedding)
        except Exception as e:
            logger.error(f"Failed to embed chunk {i}: {e}")
            # Return zero vector as fallback
            embeddings.append([0.0] * settings.EMBEDDING_DIM)

    return embeddings


def embed_all_chunks(batch_size: int = 100) -> int:
    """Embed all chunks that don't have embeddings yet.

    Args:
        batch_size: Number of chunks to process at a time

    Returns:
        Number of chunks embedded
    """
    from apps.ledger.models import Chunk

    chunks = Chunk.objects.filter(embedding__isnull=True).order_by("id")
    total = chunks.count()

    if total == 0:
        logger.info("No chunks to embed")
        return 0

    logger.info(f"Embedding {total} chunks...")
    embedded = 0

    for chunk in chunks.iterator(chunk_size=batch_size):
        try:
            embedding = get_embedding(chunk.text)
            chunk.embedding = embedding
            chunk.save(update_fields=["embedding", "updated_at"])
            embedded += 1

            if embedded % 50 == 0:
                logger.info(f"Embedded {embedded}/{total} chunks")

        except Exception as e:
            logger.error(f"Failed to embed chunk {chunk.id}: {e}")

    logger.info(f"Finished embedding {embedded} chunks")
    return embedded


def check_ollama_connection() -> bool:
    """Check if Ollama is reachable and model is available."""
    try:
        response = httpx.get(
            f"{settings.OLLAMA_URL}/api/tags",
            timeout=5.0,
        )
        response.raise_for_status()

        data = response.json()
        models = [m["name"] for m in data.get("models", [])]

        embed_model = settings.OLLAMA_EMBED_MODEL
        if embed_model not in models and f"{embed_model}:latest" not in models:
            logger.warning(f"Embedding model {embed_model} not found in Ollama")
            return False

        return True

    except Exception as e:
        logger.warning(f"Ollama connection check failed: {e}")
        return False
