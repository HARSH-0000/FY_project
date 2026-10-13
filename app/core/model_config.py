"""
Centralized Model Configuration for Irium Multi-Agent System.

Assigns Groq models by task category:
- Simple routing: Deterministic Python rules (no LLM)
- Lightweight classification / standard QA / summaries / extraction: openai/gpt-oss-20b
- Complex financial research / synthesis / complex document reasoning: openai/gpt-oss-120b
- Alternative model for suitable tasks / fallback: qwen/qwen3.8-27b
- Ultimate fallback: Google Gemini (if GOOGLE_API_KEY is configured)
"""

from enum import Enum
from typing import Dict, Any, List, Tuple
from app.core import settings


class TaskType(str, Enum):
    ROUTING = "routing"
    LIGHTWEIGHT = "lightweight"
    QA_STANDARD = "qa_standard"
    SUMMARIZATION = "summarization"
    SYNTHESIS_COMPLEX = "synthesis_complex"
    DOCUMENT_REASONING = "document_reasoning"
    VERIFICATION = "verification"


class ModelConfig:
    """Centralized policy and parameters for LLM task assignment."""

    @staticmethod
    def get_model_for_task(task_type: TaskType) -> str:
        """Return the preferred model for a given task based on settings."""
        if settings.LLM_PROVIDER == "google":
            return settings.LLM_MODEL or "gemini-1.5-flash"

        # Groq model routing
        if task_type in (TaskType.SYNTHESIS_COMPLEX, TaskType.DOCUMENT_REASONING):
            return settings.GROQ_MODEL_COMPLEX  # openai/gpt-oss-120b
        elif task_type in (
            TaskType.LIGHTWEIGHT,
            TaskType.QA_STANDARD,
            TaskType.SUMMARIZATION,
            TaskType.VERIFICATION,
            TaskType.ROUTING,
        ):
            return settings.GROQ_MODEL_STANDARD  # openai/gpt-oss-20b
        
        return settings.GROQ_MODEL_STANDARD

    @staticmethod
    def get_task_parameters(task_type: TaskType) -> Dict[str, Any]:
        """Return temperature and token limits tailored to task type."""
        configs = {
            TaskType.ROUTING: {
                "temperature": 0.0,
                "max_tokens": 150,
            },
            TaskType.LIGHTWEIGHT: {
                "temperature": 0.1,
                "max_tokens": 1024,
            },
            TaskType.QA_STANDARD: {
                "temperature": 0.2,
                "max_tokens": 2048,
            },
            TaskType.SUMMARIZATION: {
                "temperature": 0.1,
                "max_tokens": 4096,
            },
            TaskType.SYNTHESIS_COMPLEX: {
                "temperature": 0.2,
                "max_tokens": 6144,  # Increased for comprehensive responses
            },
            TaskType.DOCUMENT_REASONING: {
                "temperature": 0.1,
                "max_tokens": 4096,
            },
            TaskType.VERIFICATION: {
                "temperature": 0.0,
                "max_tokens": 2048,
            },
        }
        return configs.get(task_type, {"temperature": 0.2, "max_tokens": 2048})

    @staticmethod
    def get_fallback_chain(preferred_model: str) -> List[Tuple[str, str]]:
        """
        Return the prioritized list of (provider, model) fallbacks.
        Groq: 120b -> 20b -> qwen3.8-27b -> Google Gemini
              20b -> qwen3.8-27b -> 120b -> Google Gemini
        """
        if settings.LLM_PROVIDER == "google":
            return [
                ("groq", settings.GROQ_MODEL_STANDARD),
                ("groq", settings.GROQ_MODEL_ALTERNATIVE),
                ("google", "gemini-3.8-flash"),
                ("google", "gemini-flash-latest"),
            ]

        # Primary provider is Groq
        if preferred_model == settings.GROQ_MODEL_COMPLEX:
            chain = [
                ("groq", settings.GROQ_MODEL_STANDARD),
                ("groq", settings.GROQ_MODEL_ALTERNATIVE),
            ]
        elif preferred_model == settings.GROQ_MODEL_STANDARD:
            chain = [
                ("groq", settings.GROQ_MODEL_ALTERNATIVE),
                ("groq", settings.GROQ_MODEL_COMPLEX),
            ]
        else:
            chain = [
                ("groq", settings.GROQ_MODEL_STANDARD),
                ("groq", settings.GROQ_MODEL_COMPLEX),
            ]

        # Append Google Gemini if configured
        if settings.GOOGLE_API_KEY:
            chain.extend([
                ("google", "gemini-3.6-flash"),
                ("google", "gemini-3.8-flash"),
            ])

        return chain
