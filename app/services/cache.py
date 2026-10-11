"""
Robust Redis and In-Memory Fallback Caching Service for Irium
Provides structured cache keys, TTL policies for financial data,
cache invalidation, PII protection, and metrics recording.
"""

import hashlib
import json
import time
import threading
from typing import Any, Optional, Dict, List
from app.core import logger, settings
from app.core.observability import metrics

try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    aioredis = None
    REDIS_AVAILABLE = False


class MemoryCacheBackend:
    """Thread-safe in-memory cache backend with TTL expiration."""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry["expires_at"] is not None and time.time() > entry["expires_at"]:
                del self._store[key]
                return None
            return entry["value"]

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        with self._lock:
            expires_at = (time.time() + ttl_seconds) if ttl_seconds else None
            self._store[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time()
            }
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self, pattern: Optional[str] = None) -> int:
        with self._lock:
            if not pattern or pattern == "*":
                count = len(self._store)
                self._store.clear()
                return count
            
            # Simple wildcard matching
            keys_to_delete = [
                k for k in self._store.keys()
                if pattern.replace("*", "") in k
            ]
            for k in keys_to_delete:
                del self._store[k]
            return len(keys_to_delete)

    def size(self) -> int:
        with self._lock:
            now = time.time()
            return sum(
                1 for e in self._store.values()
                if e["expires_at"] is None or e["expires_at"] > now
            )


class CacheService:
    """
    High-level caching service with Redis and automatic in-memory fallback.
    """

    def __init__(self):
        self.enabled = settings.REDIS_ENABLED
        self.redis_url = settings.REDIS_URL
        self._redis_client: Optional[Any] = None
        self._memory_fallback = MemoryCacheBackend()
        self._using_fallback = False
        self._init_client()

    def _init_client(self):
        """Initialize Redis connection if enabled and available."""
        if not self.enabled or not REDIS_AVAILABLE:
            self._using_fallback = True
            logger.info("CacheService: Using In-Memory fallback cache (Redis disabled or library not available)")
            return

        try:
            self._redis_client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0
            )
            self._using_fallback = False
            logger.info(f"CacheService: Configured for Redis at {self.redis_url}")
        except Exception as e:
            self._using_fallback = True
            logger.warning(f"CacheService: Failed to connect to Redis ({e}), falling back to In-Memory cache")

    @property
    def backend_type(self) -> str:
        """Return active cache backend type."""
        return "in_memory_fallback" if self._using_fallback else "redis"

    def build_key(self, namespace: str, query: str, **params) -> str:
        """
        Build deterministic, canonical cache key.
        irium:{namespace}:{query_hash}
        """
        clean_query = query.strip().lower()
        param_str = json.dumps(params, sort_keys=True) if params else ""
        raw_key = f"{clean_query}:{param_str}".encode("utf-8")
        query_hash = hashlib.sha256(raw_key).hexdigest()[:16]
        return f"irium:{namespace}:{query_hash}"

    def get_ttl_for_tier(self, tier: str) -> int:
        """Return appropriate TTL based on volatility of the financial tier."""
        tier_upper = tier.upper()
        if tier_upper == "SIMPLE":
            return settings.CACHE_STABLE_TTL  # 24 hours
        elif tier_upper == "VERIFICATION":
            return settings.CACHE_VOLATILE_TTL  # 5 minutes
        else:
            return settings.CACHE_DEFAULT_TTL  # 1 hour

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache with metrics recording and fallback."""
        if not self.enabled:
            metrics.record_cache_miss()
            return None

        # Try Redis first if not using fallback
        if not self._using_fallback and self._redis_client:
            try:
                data = await self._redis_client.get(key)
                if data is not None:
                    metrics.record_cache_hit()
                    return json.loads(data)
                metrics.record_cache_miss()
                return None
            except Exception as e:
                logger.warning(f"Cache get error from Redis ({e}), falling back to memory")
                self._using_fallback = True

        # In-memory fallback
        value = self._memory_fallback.get(key)
        if value is not None:
            metrics.record_cache_hit()
            return value
        
        metrics.record_cache_miss()
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """Store value in cache with TTL and fallback."""
        if not self.enabled:
            return False

        effective_ttl = ttl_seconds or settings.CACHE_DEFAULT_TTL

        # Don't cache error results
        if isinstance(value, dict) and value.get("error"):
            return False

        # Try Redis first
        if not self._using_fallback and self._redis_client:
            try:
                payload = json.dumps(value)
                await self._redis_client.set(key, payload, ex=effective_ttl)
                return True
            except Exception as e:
                logger.warning(f"Cache set error to Redis ({e}), writing to memory fallback")
                self._using_fallback = True

        # In-memory fallback
        return self._memory_fallback.set(key, value, ttl_seconds=effective_ttl)

    async def delete(self, key: str) -> bool:
        """Delete specific key."""
        if not self._using_fallback and self._redis_client:
            try:
                res = await self._redis_client.delete(key)
                return res > 0
            except Exception:
                pass
        return self._memory_fallback.delete(key)

    async def clear(self, pattern: str = "irium:*") -> int:
        """Invalidate cache keys matching pattern."""
        deleted_count = 0
        if not self._using_fallback and self._redis_client:
            try:
                keys = await self._redis_client.keys(pattern)
                if keys:
                    deleted_count = await self._redis_client.delete(*keys)
                return deleted_count
            except Exception:
                pass
        return self._memory_fallback.clear(pattern)

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache operational statistics."""
        is_redis_alive = False
        redis_info = {}
        if self._redis_client and not self._using_fallback:
            try:
                await self._redis_client.ping()
                is_redis_alive = True
            except Exception:
                is_redis_alive = False

        total_lookups = metrics.cache_hits + metrics.cache_misses
        hit_rate = (metrics.cache_hits / total_lookups * 100) if total_lookups > 0 else 0.0

        return {
            "backend": self.backend_type,
            "redis_connected": is_redis_alive,
            "enabled": self.enabled,
            "memory_cache_items": self._memory_fallback.size(),
            "hits": metrics.cache_hits,
            "misses": metrics.cache_misses,
            "hit_rate_pct": round(hit_rate, 2),
            "ttls": {
                "stable": settings.CACHE_STABLE_TTL,
                "default": settings.CACHE_DEFAULT_TTL,
                "volatile": settings.CACHE_VOLATILE_TTL
            }
        }


# Global cache service instance
cache_service = CacheService()
