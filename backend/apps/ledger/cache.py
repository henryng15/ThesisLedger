"""Redis cache-aside implementation for analysis job deduplication.

Uses Redis to cache job results by thesis+company hash, avoiding
redundant analysis runs for the same input.
"""

import logging
from typing import Optional

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# Lazy connection - initialized on first use
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
        )
    return _redis_client


def get_cached_job_id(cache_key: str) -> Optional[str]:
    """Look up cached job ID for the given cache key.

    Args:
        cache_key: SHA-256 hash of thesis text + company ticker

    Returns:
        Job ID if cached, None otherwise
    """
    try:
        client = get_redis_client()
        job_id = client.get(f"analysis:{cache_key}")
        if job_id:
            logger.debug(f"Cache hit for {cache_key[:16]}...")
        return job_id
    except redis.RedisError as e:
        logger.warning(f"Redis get failed: {e}")
        return None


def set_cached_job_id(cache_key: str, job_id: str, ttl: int = 3600) -> bool:
    """Cache a job ID with expiration.

    Args:
        cache_key: SHA-256 hash of thesis text + company ticker
        job_id: UUID of the completed job
        ttl: Time to live in seconds (default 1 hour)

    Returns:
        True if cached successfully
    """
    try:
        client = get_redis_client()
        client.setex(f"analysis:{cache_key}", ttl, job_id)
        logger.debug(f"Cached job {job_id} for {cache_key[:16]}...")
        return True
    except redis.RedisError as e:
        logger.warning(f"Redis set failed: {e}")
        return False


def invalidate_cache(cache_key: str) -> bool:
    """Remove a cached job result.

    Args:
        cache_key: SHA-256 hash to invalidate

    Returns:
        True if key was deleted
    """
    try:
        client = get_redis_client()
        deleted = client.delete(f"analysis:{cache_key}")
        return deleted > 0
    except redis.RedisError as e:
        logger.warning(f"Redis delete failed: {e}")
        return False


def ping() -> bool:
    """Check Redis connectivity."""
    try:
        client = get_redis_client()
        return client.ping()
    except redis.RedisError:
        return False
