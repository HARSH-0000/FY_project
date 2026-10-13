"""
Global Rate Limiter and Concurrency Control for LLM Providers.

Implements:
1. Process-global concurrency control via asyncio.Semaphore (default 2 concurrent calls)
2. Process-global requests-per-minute (RPM) rate limiter (sliding window)
3. Non-blocking asynchronous admission control
4. Compatible with multi-worker deployments (documents process-local boundary with optional Redis hook)
"""

import time
import asyncio
from typing import Optional
from collections import deque
from app.core import logger, settings


class GlobalRateLimiter:
    """
    Coordinates global concurrency and request rates across all LLM models and nodes.
    Ensures burst requests do not overwhelm the Groq API.
    """

    def __init__(
        self,
        max_concurrency: Optional[int] = None,
        requests_per_minute: Optional[int] = None,
    ):
        self.max_concurrency = max_concurrency or settings.LLM_GLOBAL_CONCURRENCY
        self.requests_per_minute = requests_per_minute or settings.LLM_REQUESTS_PER_MINUTE
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._request_timestamps: deque = deque()
        self._lock: Optional[asyncio.Lock] = None

    def _ensure_async_primitives(self):
        """Ensure asyncio primitives are created within an active event loop."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 0) -> float:
        """
        Acquire permission to execute an LLM call.
        Enforces both concurrency (semaphore) and rate limit (RPM).
        Returns the duration waited in seconds.
        """
        self._ensure_async_primitives()
        start_wait = time.time()

        # 1. Acquire concurrency slot (max 2 parallel requests by default)
        await self._semaphore.acquire()

        # 2. Check and throttle against RPM sliding window
        async with self._lock:
            now = time.time()
            one_minute_ago = now - 60.0

            # Prune timestamps older than 60s
            while self._request_timestamps and self._request_timestamps[0] <= one_minute_ago:
                self._request_timestamps.popleft()

            # If at or above rate limit, calculate necessary non-blocking sleep
            if len(self._request_timestamps) >= self.requests_per_minute:
                oldest_in_window = self._request_timestamps[0]
                sleep_duration = max(0.05, 60.0 - (now - oldest_in_window) + 0.1)
                logger.info(f"RateLimiter: RPM limit reached ({len(self._request_timestamps)}/{self.requests_per_minute}). Throttling for {sleep_duration:.2f}s")
                await asyncio.sleep(sleep_duration)
                
                # Re-prune after waking
                now = time.time()
                one_minute_ago = now - 60.0
                while self._request_timestamps and self._request_timestamps[0] <= one_minute_ago:
                    self._request_timestamps.popleft()

            self._request_timestamps.append(time.time())

        wait_time = time.time() - start_wait
        return wait_time

    def release(self):
        """Release the concurrency slot."""
        if self._semaphore is not None:
            self._semaphore.release()


# Global rate limiter singleton
rate_limiter = GlobalRateLimiter()
