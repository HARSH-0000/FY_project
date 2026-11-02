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
from app.core import logger


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


class SpanContext:
    """Context manager for tracing operations."""

    def __init__(self, name: str, attributes: Optional[Dict[str, Any]] = None, **kwargs):
        self.name = name
        self.attributes = dict(attributes) if attributes and isinstance(attributes, dict) else {}
        if kwargs:
            self.attributes.update(kwargs)
        self.span: Optional[Span] = None

    def __enter__(self) -> Span:
        trace_id = get_current_trace_id()
        span_id = f"sp-{uuid.uuid4().hex[:8]}"
        self.span = Span(
            name=self.name,
            trace_id=trace_id,
            span_id=span_id,
            start_time=time.time(),
            attributes=self.attributes
        )
        logger.debug(f"[TRACE] Starting span: {self.name} (trace_id: {trace_id})")
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
        logger.debug(f"[TRACE] Completed span: {self.name} in {self.span.duration_ms:.2f}ms")
        return False  # Do not suppress exception


def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None, **kwargs) -> SpanContext:
    """
    Factory function for SpanContext.
    Supports:
        trace_span("operation_name")
        trace_span("operation_name", {"attr": "value"})
        trace_span("operation_name", key="value")
        trace_span("operation_name", {"attr": "value"}, extra="key")
    """
    attrs = dict(attributes) if attributes and isinstance(attributes, dict) else {}
    if kwargs:
        attrs.update(kwargs)
    return SpanContext(name, attrs)


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
            self.max_spans: int = 200
            self._counters: Dict[str, int] = defaultdict(int)
            self._timings: Dict[str, list] = defaultdict(list)
            self._gauges: Dict[str, float] = {}

    def increment_counter(self, name: str, value: int = 1, **labels):
        """Increment a counter metric."""
        with self._lock:
            key = f"{name}:{':'.join(f'{k}={v}' for k, v in sorted(labels.items()))}" if labels else name
            self._counters[key] += value

    def record_timing(self, name: str, duration_ms: float, **labels):
        """Record a timing metric."""
        with self._lock:
            key = f"{name}:{':'.join(f'{k}={v}' for k, v in sorted(labels.items()))}" if labels else name
            self._timings[key].append(duration_ms)

    def set_gauge(self, name: str, value: float, **labels):
        """Set a gauge metric."""
        with self._lock:
            key = f"{name}:{':'.join(f'{k}={v}' for k, v in sorted(labels.items()))}" if labels else name
            self._gauges[key] = value

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float):
        with self._lock:
            key = f"{method} {path} [{status_code}]"
            self.request_counts[key] += 1
            dur_list = self.request_durations[key]
            dur_list.append(duration_ms)
            if len(dur_list) > 1000:
                dur_list.pop(0)

            req_key = f"http_requests:method={method}:path={path}:status={status_code}"
            self._counters[req_key] += 1
            time_key = f"http_duration_ms:method={method}:path={path}"
            self._timings[time_key].append(duration_ms)

    def record_agent_execution(self, agent_name: str, duration_ms: float, status: str = "success"):
        with self._lock:
            key = f"{agent_name}:{status}"
            self.agent_counts[key] += 1
            dur_list = self.agent_durations[agent_name]
            dur_list.append(duration_ms)
            if len(dur_list) > 500:
                dur_list.pop(0)

            c_key = f"agent_executions:agent={agent_name}:status={status}"
            self._counters[c_key] += 1
            t_key = f"agent_duration_ms:agent={agent_name}"
            self._timings[t_key].append(duration_ms)

    def record_llm_call(self, *args, **kwargs):
        """
        Record LLM call metrics.
        Supported signatures:
        - record_llm_call(provider, model, duration_ms, status="success")
        - record_llm_call(model, duration_ms, tokens=0)
        - record_llm_call(model="gemini", duration_ms=120.0, ...)
        """
        with self._lock:
            provider = "default"
            model = "unknown"
            duration_ms = 0.0
            status = kwargs.get("status", "success")
            tokens = kwargs.get("tokens", 0)

            if len(args) >= 3 and isinstance(args[2], (int, float)):
                provider = str(args[0])
                model = str(args[1])
                duration_ms = float(args[2])
                if len(args) >= 4 and isinstance(args[3], str):
                    status = args[3]
            elif len(args) == 2 and isinstance(args[1], (int, float)):
                model = str(args[0])
                duration_ms = float(args[1])
            elif len(args) == 1:
                model = str(args[0])

            if "provider" in kwargs:
                provider = str(kwargs["provider"])
            if "model" in kwargs:
                model = str(kwargs["model"])
            if "duration_ms" in kwargs:
                duration_ms = float(kwargs["duration_ms"])

            key = f"{provider}/{model}:{status}" if provider != "default" else f"{model}:{status}"
            self.llm_counts[key] += 1
            dur_key = f"{provider}/{model}" if provider != "default" else model
            dur_list = self.llm_durations[dur_key]
            dur_list.append(duration_ms)
            if len(dur_list) > 500:
                dur_list.pop(0)

            call_key = f"llm_calls:model={model}:provider={provider}"
            self._counters[call_key] += 1
            time_key = f"llm_duration_ms:model={model}:provider={provider}"
            self._timings[time_key].append(duration_ms)
            if tokens > 0:
                tok_key = f"llm_tokens:model={model}"
                self._counters[tok_key] += tokens

    def record_retrieval(self, duration_ms: float):
        with self._lock:
            self.retrieval_durations.append(duration_ms)
            if len(self.retrieval_durations) > 500:
                self.retrieval_durations.pop(0)
            self._counters["retrievals"] += 1
            self._timings["retrieval_duration_ms"].append(duration_ms)

    def record_search_call(self, duration_ms: float, result_count: int = 0):
        with self._lock:
            self.retrieval_durations.append(duration_ms)
            if len(self.retrieval_durations) > 500:
                self.retrieval_durations.pop(0)
            self._counters["search_calls"] += 1
            self._timings["search_duration_ms"].append(duration_ms)
            if result_count > 0:
                self._gauges["search_results"] = float(result_count)

    def record_workflow(self, duration_ms: float, workflow_name: str = "research", status: str = "success"):
        with self._lock:
            self.workflow_durations.append(duration_ms)
            if len(self.workflow_durations) > 500:
                self.workflow_durations.pop(0)
            w_key = f"workflow_executions:status={status}:workflow={workflow_name}"
            self._counters[w_key] += 1
            wt_key = f"workflow_duration_ms:workflow={workflow_name}"
            self._timings[wt_key].append(duration_ms)

    def record_cache_hit(self, cache_type: str = "default", *args, **kwargs):
        with self._lock:
            self.cache_hits += 1
            self._counters[f"cache_hits:type={cache_type}"] += 1

    def record_cache_miss(self, cache_type: str = "default", *args, **kwargs):
        with self._lock:
            self.cache_misses += 1
            self._counters[f"cache_misses:type={cache_type}"] += 1

    def record_cache_set(self, cache_type: str = "default", *args, **kwargs):
        with self._lock:
            self._counters[f"cache_sets:type={cache_type}"] += 1

    def record_error(self, component: str, error_type: str = "Error", *args, **kwargs):
        with self._lock:
            self.errors_by_type[f"{component}:{error_type}"] += 1
            self._counters[f"errors:class_name={error_type}:type={component}"] += 1

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

    def get_counters(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def get_timings(self) -> Dict[str, Dict[str, float]]:
        with self._lock:
            stats = {}
            for key, values in self._timings.items():
                if values:
                    stats[key] = {
                        "count": len(values),
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                    }
            return stats

    def get_gauges(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._gauges)

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
                "counters": dict(self._counters),
                "timings": {
                    key: {
                        "count": len(values),
                        "avg": round(sum(values) / len(values), 2) if values else 0.0,
                        "min": round(min(values), 2) if values else 0.0,
                        "max": round(max(values), 2) if values else 0.0,
                    }
                    for key, values in self._timings.items()
                },
                "gauges": dict(self._gauges),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global metrics registry
metrics = MetricsRegistry()
# Backwards-compatibility alias
MetricsCollector = MetricsRegistry
