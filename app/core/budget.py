"""
Per-Request Budget and Context Tracking for Irium Multi-Agent System.

Prevents infinite agent loops, runaway API calls, and resource exhaustion.
Enforces strict per-request budgets:
- Max LLM calls (default 5)
- Max tool executions (default 3)
- Max retries (default 2)
- Max graph iterations (default 2)
- Max execution time (default 30s)

Thread-safe and contextvar-isolated: no cross-request counter leakage.
"""

import time
import contextvars
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from app.core import logger, settings


class BudgetExceededError(Exception):
    """Raised when a request exceeds its allotted resource budget."""
    def __init__(self, resource: str, current: int, limit: int):
        super().__init__(f"Request budget exceeded for '{resource}': {current} >= limit {limit}")
        self.resource = resource
        self.current = current
        self.limit = limit


@dataclass
class RequestBudget:
    """Tracks resource consumption for a single request lifecycle."""
    request_id: str
    max_llm_calls: int = field(default_factory=lambda: settings.BUDGET_MAX_LLM_CALLS)
    max_tool_executions: int = field(default_factory=lambda: settings.BUDGET_MAX_TOOL_EXECUTIONS)
    max_retries: int = field(default_factory=lambda: settings.BUDGET_MAX_RETRIES)
    max_graph_iterations: int = field(default_factory=lambda: settings.BUDGET_MAX_GRAPH_ITERATIONS)
    timeout_seconds: float = field(default_factory=lambda: settings.BUDGET_TIMEOUT_SECONDS)
    
    start_time: float = field(default_factory=time.time)
    llm_calls: int = 0
    retries: int = 0
    tool_executions: int = 0
    graph_iterations: int = 0
    total_tokens_estimated: int = 0
    rate_limit_waits: int = 0
    total_wait_seconds: float = 0.0
    best_valid_answer: Optional[str] = None
    outcome: str = "in_progress"

    def check_time(self):
        """Check if request execution deadline has elapsed."""
        elapsed = time.time() - self.start_time
        if elapsed > self.timeout_seconds:
            self.outcome = "timeout"
            raise BudgetExceededError("execution_time", int(elapsed), int(self.timeout_seconds))

    def record_llm_call(self, estimated_tokens: int = 0):
        """Record an LLM call attempt against budget."""
        self.check_time()
        if self.llm_calls >= self.max_llm_calls:
            self.outcome = "budget_exhausted"
            raise BudgetExceededError("llm_calls", self.llm_calls + 1, self.max_llm_calls)
        self.llm_calls += 1
        self.total_tokens_estimated += estimated_tokens

    def record_retry(self):
        """Record an LLM retry attempt."""
        self.check_time()
        if self.retries >= self.max_retries:
            self.outcome = "retries_exhausted"
            raise BudgetExceededError("retries", self.retries + 1, self.max_retries)
        self.retries += 1

    def record_tool_execution(self):
        """Record a tool execution (search, document retrieval, etc.)."""
        self.check_time()
        if self.tool_executions >= self.max_tool_executions:
            self.outcome = "tool_budget_exhausted"
            raise BudgetExceededError("tool_executions", self.tool_executions + 1, self.max_tool_executions)
        self.tool_executions += 1

    def record_graph_iteration(self):
        """Record a graph iteration loop."""
        self.check_time()
        if self.graph_iterations >= self.max_graph_iterations:
            self.outcome = "iterations_exhausted"
            raise BudgetExceededError("graph_iterations", self.graph_iterations + 1, self.max_graph_iterations)
        self.graph_iterations += 1

    def record_rate_limit_wait(self, duration: float):
        """Record a rate-limit sleep interval."""
        self.rate_limit_waits += 1
        self.total_wait_seconds += duration

    def set_best_answer(self, answer: str):
        """Save best valid answer generated so far."""
        if answer and answer.strip():
            self.best_valid_answer = answer

    def can_make_optional_call(self) -> bool:
        """Check if remaining budget permits an optional agent call (e.g. reflection/critic)."""
        elapsed = time.time() - self.start_time
        return (
            self.llm_calls < self.max_llm_calls
            and (self.max_llm_calls - self.llm_calls) >= 1
            and elapsed < (self.timeout_seconds * 0.8)
        )

    def summary(self) -> str:
        """Return human-readable and structured summary for observability."""
        return (
            f"Request: {self.request_id}\n"
            f"Model calls: {self.llm_calls}\n"
            f"Retries: {self.retries}\n"
            f"Tool executions: {self.tool_executions}\n"
            f"Total tokens: {self.total_tokens_estimated}\n"
            f"Rate-limit waits: {self.rate_limit_waits}\n"
            f"Outcome: {self.outcome}"
        )


# Async context-local storage for RequestBudget
_current_budget: contextvars.ContextVar[Optional[RequestBudget]] = contextvars.ContextVar(
    "current_budget", default=None
)


def get_current_budget() -> Optional[RequestBudget]:
    """Retrieve the budget active for the current async execution context."""
    return _current_budget.get()


def set_current_budget(budget: RequestBudget) -> None:
    """Set the active budget for the current async execution context."""
    _current_budget.set(budget)


def start_request_budget(
    request_id: str,
    max_llm_calls: Optional[int] = None,
    max_tool_executions: Optional[int] = None,
    max_retries: Optional[int] = None,
    timeout_seconds: Optional[float] = None
) -> RequestBudget:
    """Initialize a fresh budget scoped to this request."""
    budget = RequestBudget(
        request_id=request_id,
        max_llm_calls=max_llm_calls or settings.BUDGET_MAX_LLM_CALLS,
        max_tool_executions=max_tool_executions or settings.BUDGET_MAX_TOOL_EXECUTIONS,
        max_retries=max_retries or settings.BUDGET_MAX_RETRIES,
        timeout_seconds=timeout_seconds or settings.BUDGET_TIMEOUT_SECONDS
    )
    set_current_budget(budget)
    return budget
