# Irium Observability Specification and Guide

## Overview
Irium includes an application observability framework covering distributed request tracing, operation-level span profiling, agent execution duration metrics, LLM call monitoring, search retrieval latency, cache telemetry, and health readiness diagnostics.

---

## Observability Capabilities

### 1. Correlation & Trace IDs
Every incoming HTTP request is stamped with a unique trace ID (e.g. `tr-a1b2c3d4e5f6`).
- **Client Propagation**: If a client supplies `X-Trace-ID` or `X-Correlation-ID`, Irium adopts and propagates it across downstream operations.
- **Response Headers**:
  - `X-Trace-ID`: Active trace identifier for the request.
  - `X-Response-Time-Ms`: End-to-end request duration in milliseconds.

### 2. Operational Metrics
Thread-safe metrics registry capturing:
- **HTTP Latency**: Request counts and statistical distribution (`avg_ms`, `min_ms`, `max_ms`, `p95_ms`) grouped by method, path, and HTTP status code.
- **Agent Execution**: Execution duration profiled across each LangGraph node:
  - `router`
  - `simple`
  - `verification`
  - `planner`
  - `reader`
  - `evidence`
  - `writer`
  - `critic`
- **LLM Performance**: Latency and success/fallback counts by model (e.g. `groq/openai/gpt-oss-120b`, `google/gemini-1.5-flash`).
- **Retrieval Duration**: Web search latency (Tavily) and document parsing times.
- **Cache Hit / Miss Rates**: Tracking cache hits, misses, and hit rate percentage.
- **Workflow End-to-End Latency**: Total time to complete multi-agent research dossiers.
- **Error Tracking**: Component and error class categorization.

---

## Available Observability Endpoints

### 1. `GET /health/ready`
Detailed readiness probe checking:
- LLM provider and credentials configuration
- Search provider readiness
- Database connection status
- Observability tracking health

### 2. `GET /api/observability/metrics`
Returns complete JSON metrics summary:
```json
{
  "http_requests": {
    "total": 42,
    "latencies": { ... }
  },
  "agent_executions": {
    "latencies_by_agent": {
      "router": { "avg_ms": 120.4, "p95_ms": 180.2, "count": 10 }
    }
  },
  "cache": {
    "hits": 15,
    "misses": 5,
    "hit_rate_pct": 75.0
  }
}
```

### 3. `GET /api/observability/traces?limit=50`
Returns the recent execution spans for inspection and debugging.

### 4. `POST /api/observability/reset`
Resets accumulated counters and histograms (for test runs and benchmarking).
