"""
Enhanced LLM Service for Irium Multi-Agent System.

Optimized for Groq API Rate Limits:
- Global concurrency limiter (Semaphore) and RPM throttler
- Robust HTTP 429 backoff with Retry-After header / message parsing
- Explicit differentiation between HTTP 429 and HTTP 400 (tool_use_failed)
- Integration with RequestBudget to prevent runaway loops
- Task-based model selection:
    * openai/gpt-oss-120b: Complex synthesis and financial reasoning
    * openai/gpt-oss-20b: Standard QA, summaries, extraction, and verification
    * qwen/qwen3.8-27b: Alternative / fallback model
    * Google Gemini: Ultimate fallback if configured
- Client reuse and caching to avoid repeated client allocations
"""

import time
import re
import random
import asyncio
from typing import Optional, List, Tuple
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage

from app.core import settings, logger
from app.core.model_config import ModelConfig, TaskType
from app.core.budget import get_current_budget
from app.services.rate_limiter import rate_limiter
from app.core.observability import trace_span, metrics


class LLMService:
    """LLM service providing coordinated rate limiting, retries, and task-based model selection."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.default_model = settings.LLM_MODEL
        self._client_cache: dict[str, Any] = {}
        self._model_cooldowns: dict[str, float] = {}

    def _mark_model_cooldown(self, provider: str, model: str, duration_seconds: float = 45.0):
        """Mark a model as cooling down due to rate limits or quota exhaustion."""
        key = f"{provider}:{model}"
        self._model_cooldowns[key] = time.time() + duration_seconds
        logger.warning(f"Model '{key}' marked in cooldown for {int(duration_seconds)}s.")

    def _is_model_available(self, provider: str, model: str) -> bool:
        """Check if a specific model is available and not cooling down."""
        key = f"{provider}:{model}"
        cooldown_until = self._model_cooldowns.get(key, 0.0)
        if time.time() < cooldown_until:
            remaining = int(cooldown_until - time.time())
            logger.info(f"Model '{key}' is on cooldown ({remaining}s remaining). Skipping.")
            return False
        return True

    def get_llm(
        self,
        temperature: float = 0.0,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None
    ):
        """Get or reuse a cached LLM instance."""
        provider_to_use = provider or self.provider
        model_to_use = model or (
            ModelConfig.get_model_for_task(TaskType.QA_STANDARD)
            if provider_to_use == "groq"
            else self.default_model
        )

        cache_key = f"{provider_to_use}:{model_to_use}:{temperature}:{max_tokens}"
        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        if provider_to_use == "google":
            if not settings.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY not configured")

            legacy_map = {
                "gemini-1.5-flash": "gemini-3.6-flash",
                "gemini-1.5-pro": "gemini-3.6-flash",
                "gemini-2.0-flash": "gemini-3.6-flash",
                "gemini-2.5-flash": "gemini-3.6-flash",
                "gemini-2.5-pro": "gemini-3.8-flash",
            }
            model_to_use = legacy_map.get(model_to_use, model_to_use)

            client = ChatGoogleGenerativeAI(
                google_api_key=settings.GOOGLE_API_KEY,
                model=model_to_use,
                temperature=temperature,
                max_output_tokens=max_tokens,
                max_retries=0
            )
        elif provider_to_use == "groq":
            if not settings.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY not configured")

            client = ChatGroq(
                groq_api_key=settings.GROQ_API_KEY,
                model_name=model_to_use,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=0  # Centralized retries handled here to prevent duplicate multiplying loops
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_to_use}")

        self._client_cache[cache_key] = client
        return client

    def _parse_retry_delay(self, error_message: str, default_backoff: float) -> float:
        """Extract retry wait time from error message or provider headers."""
        # Check patterns like "Please try again in 11.6175s" or "try again in 5s"
        match = re.search(r'try again in ([0-9.]+)\s*s', error_message, re.IGNORECASE)
        if match:
            try:
                seconds = float(match.group(1)) + 0.5  # Add 0.5s safety margin
                return min(seconds, 30.0)
            except ValueError:
                pass
        return default_backoff

    async def invoke(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Invoke LLM with task-based selection, global rate limiting, budget enforcement,
        and bounded 429 backoff.
        """
        # Determine model and task parameters
        if task_type:
            task_params = ModelConfig.get_task_parameters(task_type)
            if temperature is None:
                temperature = task_params["temperature"]
            if max_tokens is None:
                max_tokens = task_params["max_tokens"]
            if model is None:
                model = ModelConfig.get_model_for_task(task_type)

        temperature = temperature if temperature is not None else 0.0
        primary_model = model or (
            ModelConfig.get_model_for_task(TaskType.QA_STANDARD)
            if self.provider == "groq"
            else self.default_model
        )

        estimated_input_tokens = (len(system_prompt) + len(user_message)) // 4
        budget = get_current_budget()

        # Build execution attempt chain (primary, then fallback models)
        execution_chain: List[Tuple[str, str]] = []
        if self._is_model_available(self.provider, primary_model):
            execution_chain.append((self.provider, primary_model))

        for fb_prov, fb_mod in ModelConfig.get_fallback_chain(primary_model):
            if (fb_prov, fb_mod) not in execution_chain and self._is_model_available(fb_prov, fb_mod):
                execution_chain.append((fb_prov, fb_mod))

        if not execution_chain:
            logger.error("No LLM models currently available (all in cooldown).")
            if budget and budget.best_valid_answer:
                return budget.best_valid_answer
            raise Exception("All available LLM models are currently rate limited or in cooldown.")

        last_exception = None

        for provider, model_name in execution_chain:
            # Maximum 2 retries per model on HTTP 429
            max_retries = settings.LLM_MAX_RETRY_ATTEMPTS
            attempt = 0

            while attempt <= max_retries:
                # Check request budget before calling
                if budget:
                    try:
                        budget.record_llm_call(estimated_tokens=estimated_input_tokens)
                    except Exception as be:
                        logger.warning(f"LLM call aborted: {be}")
                        if budget.best_valid_answer:
                            return budget.best_valid_answer
                        raise

                # Acquire global concurrency and RPM slot
                wait_duration = await rate_limiter.acquire(estimated_tokens=estimated_input_tokens)
                if budget and wait_duration > 0:
                    budget.record_rate_limit_wait(wait_duration)

                start_time = time.time()
                try:
                    logger.info(f"Invoking {provider}/{model_name} (attempt {attempt + 1})")
                    llm = self.get_llm(
                        temperature=temperature,
                        model=model_name,
                        provider=provider,
                        max_tokens=max_tokens
                    )

                    messages = [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_message)
                    ]

                    with trace_span(f"llm:{provider}/{model_name}"):
                        response = await llm.ainvoke(messages)

                    duration_ms = (time.time() - start_time) * 1000
                    metrics.record_llm_call(provider, model_name, duration_ms, status="success")

                    content = response.content if hasattr(response, "content") else str(response)
                    if budget:
                        budget.set_best_answer(content)
                    return content

                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    metrics.record_llm_call(provider, model_name, duration_ms, status="error")
                    error_str = str(e)
                    last_exception = e

                    # Check for HTTP 400 (e.g. tool_use_failed) - DO NOT treat as rate limit
                    is_tool_error = "tool_use_failed" in error_str or "Tool choice is none" in error_str or "invalid_request_error" in error_str
                    if is_tool_error:
                        logger.warning(f"HTTP 400 Tool/Request format error for {provider}/{model_name}: {e}. Not a rate limit, switching model.")
                        break  # Stop retrying this model, proceed to fallback

                    # Check for rate limit / 429 / quota error
                    is_rate_limit = (
                        "rate_limit" in error_str.lower()
                        or "429" in error_str
                        or "resourceexhausted" in error_str.lower()
                        or "quota" in error_str.lower()
                        or "tpd" in error_str.lower()
                        or "tpm" in error_str.lower()
                    )

                    if is_rate_limit:
                        attempt += 1
                        # Mark cooldown for daily quota limits
                        if "tpd" in error_str.lower() or "day" in error_str.lower():
                            self._mark_model_cooldown(provider, model_name, 1800.0)
                            break  # Daily quota exhausted, immediately switch model

                        if attempt <= max_retries:
                            if budget:
                                try:
                                    budget.record_retry()
                                except Exception as be:
                                    logger.warning(f"Retry budget reached ({be}).")
                                    if budget.best_valid_answer:
                                        return budget.best_valid_answer
                                    break
                            # Calculate backoff delay
                            base_delay = settings.LLM_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                            jitter = random.uniform(0.1, 0.5)
                            delay = self._parse_retry_delay(error_str, base_delay + jitter)

                            logger.warning(f"HTTP 429 on {provider}/{model_name}. Retrying in {delay:.2f}s (retry {attempt}/{max_retries})...")
                            if budget:
                                budget.record_rate_limit_wait(delay)
                            await asyncio.sleep(delay)
                            continue
                        else:
                            # Retries exhausted for this model
                            self._mark_model_cooldown(provider, model_name, 30.0)
                            logger.warning(f"Retries exhausted on {provider}/{model_name}. Switching to next available model.")
                            break
                    else:
                        # Other non-retryable error (e.g. auth, bad model parameter)
                        logger.warning(f"Non-rate-limit error on {provider}/{model_name}: {e}")
                        break

                finally:
                    rate_limiter.release()

        # If all models in the chain failed
        logger.error(f"All LLM models in execution chain failed. Last error: {last_exception}")
        if budget and budget.best_valid_answer:
            logger.info("Returning previously saved best valid answer despite error.")
            return budget.best_valid_answer

        raise last_exception or Exception("All available LLM models failed or exceeded rate limits.")


# Global LLM service singleton
llm_service = LLMService()
