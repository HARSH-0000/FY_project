"""
Cache management API router for stats, clearing, and invalidation.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.cache import cache_service

router = APIRouter()


class InvalidateRequest(BaseModel):
    namespace: Optional[str] = None
    query: Optional[str] = None
    key: Optional[str] = None


@router.get("/api/cache/stats")
async def get_cache_stats():
    """Retrieve operational statistics and health of the caching layer."""
    return await cache_service.get_stats()


@router.post("/api/cache/clear")
async def clear_cache(pattern: Optional[str] = "irium:*"):
    """Clear all or pattern-matching cached entries."""
    deleted = await cache_service.clear(pattern=pattern or "irium:*")
    return {
        "status": "cleared",
        "keys_deleted": deleted,
        "pattern": pattern
    }


@router.post("/api/cache/invalidate")
async def invalidate_entry(request: InvalidateRequest):
    """Invalidate a specific cache key or query."""
    if request.key:
        success = await cache_service.delete(request.key)
        return {"status": "deleted" if success else "not_found", "key": request.key}
    
    if request.namespace and request.query:
        key = cache_service.build_key(request.namespace, request.query)
        success = await cache_service.delete(key)
        return {"status": "deleted" if success else "not_found", "key": key}

    return {"status": "error", "message": "Specify either 'key' or both 'namespace' and 'query'"}
