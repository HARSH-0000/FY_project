# Irium Redis-Based Caching Specification

## Overview
Irium integrates a multi-tiered caching layer with Redis and automatic in-memory fallback. It prevents redundant computation, diminishes external API calls (LLMs & search), reduces request latency, and tracks cache hit/miss performance.

---

## Architecture & Tier-Based TTL Strategy

Financial research encompasses diverse information volatility. Irium employs tier-differentiated TTLs:

| Tier / Category | Volatility | TTL Duration | Examples |
| :--- | :--- | :--- | :--- |
| **`SIMPLE`** | Low (Stable financial definitions) | **86,400s (24 Hours)** | *"What is EBITDA?"*, *"Explain Debt-to-Equity ratio"*, *"Define NPA"* |
| **`VERIFICATION`** | High (Time-sensitive market facts) | **300s (5 Minutes)** | *"Current RBI repo rate"*, *"Latest Fed funds rate"*, *"Live market rates"* |
| **`COMPLEX`** | Medium (Deep multi-agent research dossiers) | **3,600s (1 Hour)** | *"Compare HDFC and ICICI financial performance and loan growth"* |
| **`SEARCH`** | Medium (Tavily search queries) | **1,800s (30 Minutes)** | Web search snippets and domain rankings |

---

## Graceful Fallback Guarantee

If Redis is temporarily unavailable or not running on the host machine:
1. `CacheService` catches the timeout/connection error.
2. It transitions seamlessly to `MemoryCacheBackend` (thread-safe in-memory store with precise TTL cleanup).
3. Core research and document processing workflows continue without crashes or degraded user experiences.
4. When Redis becomes accessible, operations automatically resume using the distributed Redis store.

---

## Cache Invalidation and Refresh

- **Client Bypass**: Adding `"bypass_cache": true` in `POST /api/research` forces fresh LLM and multi-agent execution while updating the cache with fresh results.
- **Cache Management Endpoints**:
  - `GET /api/cache/stats`: Operational telemetry including active backend (`redis` vs `in_memory_fallback`), total hits, misses, hit rate percentage, and item count.
  - `POST /api/cache/clear`: Clear all entries matching `irium:*`.
  - `POST /api/cache/invalidate`: Selectively invalidate keys by query or namespace.
