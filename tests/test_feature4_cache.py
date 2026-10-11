"""
Comprehensive Test Suite for Feature 4: Redis-Based Caching and In-Memory Fallback
Tests cache writes, hits, misses, TTL expiration, invalidation, key isolation,
Redis unavailability fallback, and API endpoints.
"""

import asyncio
import time
from fastapi.testclient import TestClient
from app.main import app
from app.services.cache import cache_service, MemoryCacheBackend, CacheService
from app.core.config import settings

client = TestClient(app)


def test_cache_set_get_and_miss():
    """Verify cache writes, cache misses, and cache hits."""
    async def _run():
        await cache_service.clear()
        
        test_key = cache_service.build_key("research", "What is EBITDA?")
        
        # 1. Miss on fresh key
        val_miss = await cache_service.get(test_key)
        assert val_miss is None, "Fresh key should return None (miss)"
        
        # 2. Write
        payload = {"answer": "EBITDA is Earnings Before Interest, Taxes, Depreciation, and Amortization."}
        success = await cache_service.set(test_key, payload, ttl_seconds=60)
        assert success is True
        
        # 3. Hit on repeated read
        val_hit = await cache_service.get(test_key)
        assert val_hit is not None, "Repeated read should return cached value (hit)"
        assert val_hit["answer"] == payload["answer"]
        
    asyncio.run(_run())


def test_ttl_expiration():
    """Verify that cached entries expire after TTL elapses."""
    async def _run():
        backend = MemoryCacheBackend()
        backend.set("test_short_key", {"data": "volatile_metric"}, ttl_seconds=1)
        
        # Immediately available
        assert backend.get("test_short_key") is not None
        
        # Wait 1.1s for expiration
        time.sleep(1.1)
        
        # Now expired
        assert backend.get("test_short_key") is None
        
    asyncio.run(_run())


def test_key_isolation_across_different_queries():
    """Confirm different queries or company parameters generate distinct isolated keys."""
    key_hdfc = cache_service.build_key("research", "Compare HDFC Bank NIM")
    key_icici = cache_service.build_key("research", "Compare ICICI Bank NIM")
    key_apple = cache_service.build_key("research", "Apple Q3 revenue", year=2024)
    key_apple_2025 = cache_service.build_key("research", "Apple Q3 revenue", year=2025)
    
    assert key_hdfc != key_icici
    assert key_apple != key_apple_2025
    assert key_hdfc.startswith("irium:research:")


def test_cache_invalidation_and_clearing():
    """Test cache deletion and pattern clearing."""
    async def _run():
        k1 = cache_service.build_key("test", "query 1")
        k2 = cache_service.build_key("test", "query 2")
        
        await cache_service.set(k1, {"val": 1})
        await cache_service.set(k2, {"val": 2})
        
        assert await cache_service.get(k1) is not None
        
        # Delete k1
        await cache_service.delete(k1)
        assert await cache_service.get(k1) is None
        assert await cache_service.get(k2) is not None
        
        # Clear all
        await cache_service.clear()
        assert await cache_service.get(k2) is None

    asyncio.run(_run())


def test_redis_unavailability_graceful_fallback():
    """Verify that if Redis connection fails or is unavailable, fallback operates smoothly."""
    async def _run():
        # Instantiate cache service pointing to a non-existent port
        original_url = settings.REDIS_URL
        try:
            settings.REDIS_URL = "redis://127.0.0.1:59999/0"  # Non-existent Redis port
            fallback_service = CacheService()
            
            # Writing and reading should still work via fallback without throwing exceptions
            test_key = fallback_service.build_key("fallback", "test query")
            saved = await fallback_service.set(test_key, {"result": "fallback_ok"}, ttl_seconds=60)
            assert saved is True
            
            val = await fallback_service.get(test_key)
            assert val is not None
            assert val.get("result") == "fallback_ok"
        finally:
            settings.REDIS_URL = original_url

    asyncio.run(_run())


def test_tier_based_ttl_strategy():
    """Verify TTL strategy assigns shorter TTL to volatile data and longer to stable definitions."""
    ttl_simple = cache_service.get_ttl_for_tier("SIMPLE")
    ttl_verification = cache_service.get_ttl_for_tier("VERIFICATION")
    ttl_complex = cache_service.get_ttl_for_tier("COMPLEX")
    
    # Stable definitional data should have longer TTL than volatile verification data
    assert ttl_simple >= 86400  # 24h
    assert ttl_verification <= 300  # 5m
    assert ttl_complex == 3600  # 1h
    assert ttl_simple > ttl_verification


def test_cache_api_stats_endpoint():
    """Verify /api/cache/stats returns current backend, counts, and hit rates."""
    response = client.get("/api/cache/stats")
    assert response.status_code == 200
    data = response.json()
    assert "backend" in data
    assert "hits" in data
    assert "misses" in data
    assert "hit_rate_pct" in data
    assert "ttls" in data


def test_cache_api_clear_endpoint():
    """Verify /api/cache/clear endpoint clears entries."""
    response = client.post("/api/cache/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleared"


if __name__ == "__main__":
    tests = [
        test_cache_set_get_and_miss,
        test_ttl_expiration,
        test_key_isolation_across_different_queries,
        test_cache_invalidation_and_clearing,
        test_redis_unavailability_graceful_fallback,
        test_tier_based_ttl_strategy,
        test_cache_api_stats_endpoint,
        test_cache_api_clear_endpoint,
    ]
    passed = 0
    for t in tests:
        print(f"Running {t.__name__}...", end=" ")
        try:
            t()
            print("PASSED")
            passed += 1
        except Exception as e:
            print(f"FAILED: {e}")
            raise
    print(f"\nAll {passed}/{len(tests)} tests passed successfully!")
