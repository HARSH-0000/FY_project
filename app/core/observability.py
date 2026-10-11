"""
Lightweight Application Observability System for Irium
Provides distributed tracing (trace IDs), execution duration profiling,
metrics collection (latencies, errors, agent durations, LLM timings, cache rates),
and non-intrusive FastAPI middleware.
"""

import time
import uuid
import contextvars
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import threading


# Context variable for async trace propagation
_current_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_trace_id", default=None
)


def get_current_trace_id() -> str:
    """Get the current trace ID or generate a new one if not present."""
    tid = _current_trace_id.get()
    if not tid:
        tid = f"tr-{uuid.uuid4().hex[:12]}"
        _current_trace_id.set(tid)
    return tid


def set_current_trace_id(trace_id: str) -> None:
    """Explicitly set current trace ID for async context."""
    _current_trace_id.set(trace_id)


@dataclass
class Span:
    """A trace span representing an individual operation or agent step."""
    name: str
    trace_id: str
    span_id: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "RUNNING"
    attributes: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class MetricsRegistry:
    """Thread-safe in-memory metrics registry for latencies, rates, and counters."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with getattr(self, "_lock", threading.Lock()):
            self.request_counts: Dict[str, int] = defaultdict(int)
            self.request_durations: Dict[str, List[float]] = defaultdict(list)
            self.agent_counts: Dict[str, int] = defaultdict(int)
            self.agent_durations: Dict[str, List[float]] = defaultdict(list)
            self.llm_counts: Dict[str, int] = defaultdict(int)
            self.llm_durations: Dict[str, List[float]] = defaultdict(list)
            self.retrieval_durations: List[float] = []
            self.workflow_durations: List[float] = []
            self.cache_hits: int = 0
            self.cache_misses: int = 0
            self.errors_by_type: Dict[str, int] = defaultdict(int)
            self.recent_spans: List[Dict[str, Any]] = []
            self.max_spans = 200

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float):
        with self._lock:
            key = f"{method} {path} [{status_code}]"
            self.request_counts[key] += 1
            dur_list = self.request_durations[key]
            dur_list.append(duration_ms)
            if len(dur_list) > 1000:
                dur_list.pop(0)

    def record_agent_execution(self, agent_name: str, duration_ms: float, status: str = "success"):
        with self._lock:
            key = f"{agent_name}:{status}"
            self.agent_counts[key] += 1
            dur_list = self.agent_durations[agent_name]
            dur_list.append(duration_ms)
            if len(dur_list) > 500:
                dur_list.pop(0)

    def record_llm_call(self, provider: str, model: str, duration_ms: float, status: str = "success"):
        with self._lock:
            key = f"{provider}/{model}:{status}"
            self.llm_counts[key] += 1
            dur_list = self.llm_durations[f"{provider}/{model}"]
            dur_list.append(duration_ms)
            if len(dur_list) > 500:
                dur_list.pop(0)

    def record_retrieval(self, duration_ms: float):
        with self._lock:
            self.retrieval_durations.append(duration_ms)
            if len(self.retrieval_durations) > 500:
                self.retrieval_durations.pop(0)

    def record_workflow(self, duration_ms: float):
        with self._lock:
            self.workflow_durations.append(duration_ms)
            if len(self.workflow_durations) > 500:
                self.workflow_durations.pop(0)

    def record_cache_hit(self):
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self):
        with self._lock:
            self.cache_misses += 1

    def record_error(self, component: str, error_type: str):
        with self._lock:
            self.errors_by_type[f"{component}:{error_type}"] += 1

    def record_span(self, span: Span):
        with self._lock:
            self.recent_spans.append({
                "name": span.name,
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "duration_ms": span.duration_ms,
                "status": span.status,
                "attributes": span.attributes,
                "error": span.error,
                "timestamp": datetime.fromtimestamp(span.start_time).isoformat()
            })
            if len(self.recent_spans) > self.max_spans:
                self.recent_spans.pop(0)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            total_cache = self.cache_hits + self.cache_misses
            cache_hit_rate = (self.cache_hits / total_cache) if total_cache > 0 else 0.0

            def _stats(arr: List[float]) -> Dict[str, float]:
                if not arr:
                    return {"count": 0, "avg_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "p95_ms": 0.0}
                sorted_arr = sorted(arr)
                p95_idx = int(len(sorted_arr) * 0.95)
                return {
                    "count": len(arr),
                    "avg_ms": round(sum(arr) / len(arr), 2),
                    "min_ms": round(min(arr), 2),
                    "max_ms": round(max(arr), 2),
                    "p95_ms": round(sorted_arr[min(p95_idx, len(sorted_arr) - 1)], 2)
                }

            agent_stats = {name: _stats(durs) for name, durs in self.agent_durations.items()}
            llm_stats = {name: _stats(durs) for name, durs in self.llm_durations.items()}

            return {
                "http_requests": {
                    "total": sum(self.request_counts.values()),
                    "counts_by_endpoint": dict(self.request_counts),
                    "latencies": {k: _stats(v) for k, v in self.request_durations.items()}
                },
                "agent_executions": {
                    "counts": dict(self.agent_counts),
                    "latencies_by_agent": agent_stats
                },
                "llm_performance": {
                    "counts": dict(self.llm_counts),
                    "latencies_by_model": llm_stats
                },
                "retrieval_performance": _stats(self.retrieval_durations),
                "workflow_performance": _stats(self.workflow_durations),
                "cache": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "total_lookups": total_cache,
                    "hit_rate_pct": round(cache_hit_rate * 100, 2)
                },
                "errors": dict(self.errors_by_type),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global metrics registry
metrics = MetricsRegistry()


class SpanContext:
    """Context manager for tracing operations."""

    def __init__(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        self.name = name
        self.attributes = attributes or {}
        self.span: Optional[Span] = None

    def __enter__(self):
        trace_id = get_current_trace_id()
        span_id = f"sp-{uuid.uuid4().hex[:8]}"
        self.span = Span(
            name=self.name,
            trace_id=trace_id,
            span_id=span_id,
            start_time=time.time(),
            attributes=self.attributes
        )
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.span:
            return False

        end_time = time.time()
        self.span.end_time = end_time
        self.span.duration_ms = round((end_time - self.span.start_time) * 1000, 2)

        if exc_type is not None:
            self.span.status = "ERROR"
            self.span.error = str(exc_val)
            metrics.record_error(self.name, exc_type.__name__)
        else:
            self.span.status = "OK"

        metrics.record_span(self.span)
        return False  # Do not suppress exception


def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Factory function for SpanContext."""
    return SpanContext(name, attributes)
