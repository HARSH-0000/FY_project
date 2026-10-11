"""
Observability API routes for metrics, traces, and readiness monitoring.
"""

from fastapi import APIRouter, Request, Response
from app.core.observability import metrics, get_current_trace_id
from app.core import settings, logger
from datetime import datetime
from typing import Dict, Any

router = APIRouter()


@router.get("/api/observability/metrics")
async def get_metrics():
    """Retrieve application metrics summary."""
    return metrics.get_summary()


@router.get("/api/observability/traces")
async def get_traces(limit: int = 50):
    """Retrieve recent execution spans/traces."""
    with metrics._lock:
        spans = list(reversed(metrics.recent_spans[-limit:]))
    return {
        "count": len(spans),
        "traces": spans
    }


@router.post("/api/observability/reset")
async def reset_metrics():
    """Reset metrics collectors (useful for testing or benchmarking)."""
    metrics.reset()
    return {"status": "reset", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness_check():
    """
    Comprehensive readiness check verifying database, LLM provider,
    and system status.
    """
    status = "ready"
    checks: Dict[str, Any] = {}

    # 1. LLM Provider configuration check
    llm_configured = False
    if settings.LLM_PROVIDER == "google" and settings.GOOGLE_API_KEY:
        llm_configured = True
    elif settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
        llm_configured = True

    checks["llm_provider"] = {
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "configured": llm_configured
    }
    if not llm_configured:
        status = "degraded"

    # 2. Search Provider check
    checks["search_provider"] = {
        "configured": bool(settings.TAVILY_API_KEY)
    }

    # 3. Database check (optional for MVP)
    try:
        from app.database import engine
        with engine.connect() as conn:
            checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"offline: {e.__class__.__name__}"
        # Database is optional in MVP local mode

    # 4. Observability status
    checks["observability"] = {
        "active_trace_id": get_current_trace_id(),
        "total_requests_tracked": sum(metrics.request_counts.values())
    }

    return {
        "status": status,
        "service": "Irium MVP",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }
