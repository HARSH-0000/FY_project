"""
Test suite for Feature 3: Application Observability
Tests correlation IDs, request timing headers, metrics summaries,
agent execution profiling, health readiness endpoint, and error tracking.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.core.observability import metrics, trace_span, get_current_trace_id
import time

client = TestClient(app)


def test_trace_id_generation_and_headers():
    """Verify incoming requests receive X-Trace-ID and X-Response-Time-Ms headers."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    assert "X-Response-Time-Ms" in response.headers
    trace_id = response.headers["X-Trace-ID"]
    assert trace_id.startswith("tr-")
    response_time = float(response.headers["X-Response-Time-Ms"])
    assert response_time >= 0.0


def test_trace_id_propagation_from_client():
    """Verify that a client-provided X-Correlation-ID is preserved and propagated."""
    custom_trace_id = "custom-audit-trace-999"
    response = client.get("/health", headers={"X-Correlation-ID": custom_trace_id})
    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == custom_trace_id


def test_metrics_endpoint():
    """Verify /api/observability/metrics returns structured operational telemetry."""
    # Reset first
    client.post("/api/observability/reset")
    
    # Make a few requests
    client.get("/health")
    client.get("/landing")
    
    response = client.get("/api/observability/metrics")
    assert response.status_code == 200
    data = response.json()
    
    assert "http_requests" in data
    assert "agent_executions" in data
    assert "llm_performance" in data
    assert "retrieval_performance" in data
    assert "cache" in data
    assert "errors" in data
    
    http_data = data["http_requests"]
    assert http_data["total"] >= 2


def test_trace_span_profiling():
    """Verify trace_span measures execution duration and records status."""
    with trace_span("test_financial_calc", {"ticker": "AAPL"}) as span:
        time.sleep(0.01)  # 10ms simulation
    
    assert span.duration_ms is not None
    assert span.duration_ms >= 5.0
    assert span.status == "OK"
    assert span.attributes["ticker"] == "AAPL"

    # Verify span recorded in traces
    response = client.get("/api/observability/traces")
    assert response.status_code == 200
    traces = response.json().get("traces", [])
    test_spans = [s for s in traces if s["name"] == "test_financial_calc"]
    assert len(test_spans) > 0
    assert test_spans[0]["status"] == "OK"


def test_agent_execution_metrics():
    """Verify agent execution durations are recorded in metrics."""
    metrics.record_agent_execution("router", 45.2, status="success")
    metrics.record_agent_execution("verification", 120.5, status="success")
    
    summary = metrics.get_summary()
    agent_execs = summary["agent_executions"]
    assert "router:success" in agent_execs["counts"]
    assert "verification:success" in agent_execs["counts"]
    assert "router" in agent_execs["latencies_by_agent"]
    assert agent_execs["latencies_by_agent"]["router"]["count"] >= 1


def test_llm_and_retrieval_metrics():
    """Verify LLM and retrieval durations are recorded."""
    metrics.record_llm_call("groq", "openai/gpt-oss-120b", 350.0, status="success")
    metrics.record_retrieval(180.0)
    
    summary = metrics.get_summary()
    assert "groq/openai/gpt-oss-120b:success" in summary["llm_performance"]["counts"]
    assert summary["retrieval_performance"]["count"] >= 1
    assert summary["retrieval_performance"]["avg_ms"] >= 100.0


def test_cache_metrics():
    """Verify cache hits, misses, and hit rate calculations."""
    metrics.record_cache_hit()
    metrics.record_cache_hit()
    metrics.record_cache_miss()
    
    summary = metrics.get_summary()
    cache_data = summary["cache"]
    assert cache_data["hits"] >= 2
    assert cache_data["misses"] >= 1
    assert cache_data["hit_rate_pct"] > 0.0


def test_health_readiness_check():
    """Verify /health/ready endpoint provides detailed diagnostic checks."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "llm_provider" in data["checks"]
    assert "search_provider" in data["checks"]
    assert "observability" in data["checks"]


def test_error_tracking():
    """Verify errors are captured without bringing down the application."""
    metrics.record_error("database", "ConnectionTimeout")
    summary = metrics.get_summary()
    assert "database:ConnectionTimeout" in summary["errors"]
    assert summary["errors"]["database:ConnectionTimeout"] >= 1


if __name__ == "__main__":
    tests = [
        test_trace_id_generation_and_headers,
        test_trace_id_propagation_from_client,
        test_metrics_endpoint,
        test_trace_span_profiling,
        test_agent_execution_metrics,
        test_llm_and_retrieval_metrics,
        test_cache_metrics,
        test_health_readiness_check,
        test_error_tracking,
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
