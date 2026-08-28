"""In-memory TTL cache for LinkedIn profile responses."""

import logging
from typing import Optional
from cachetools import TTLCache

from app.config import settings
from app.schemas.response import ProfileResponse

logger = logging.getLogger(__name__)

# In-memory cache mapping public_identifier -> ProfileResponse
_cache: Optional[TTLCache] = None


def get_cache() -> TTLCache:
    """Return singleton cache instance."""
    global _cache
    if _cache is None:
        _cache = TTLCache(
            maxsize=settings.CACHE_MAXSIZE,
            ttl=settings.CACHE_TTL_SECONDS,
        )
    return _cache


def get_cached_profile(public_id: str) -> Optional[ProfileResponse]:
    """Retrieve profile from cache if enabled and present."""
    if not settings.CACHE_ENABLED:
        return None
    cache = get_cache()
    profile = cache.get(public_id)
    if profile:
        logger.info(f"Cache HIT for profile: {public_id}")
        # Return a copy marked as cached
        copy_data = profile.model_dump()
        copy_data["is_cached"] = True
        return ProfileResponse(**copy_data)
    return None


def set_cached_profile(public_id: str, profile: ProfileResponse) -> None:
    """Store profile in cache."""
    if not settings.CACHE_ENABLED:
        return
    cache = get_cache()
    cache[public_id] = profile
    logger.info(f"Cached profile: {public_id}")


def clear_cache() -> None:
    """Clear all items from cache."""
    cache = get_cache()
    cache.clear()
