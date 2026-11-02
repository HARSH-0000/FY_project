"""
LangSmith configuration for tracing and observability.
"""
import os
from typing import Optional
from app.core import logger, settings


def initialize_langsmith():
    """
    Initialize LangSmith tracing if enabled.
    Checks for LANGCHAIN_TRACING_V2 and LANGCHAIN_API_KEY environment variables.
    """
    langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_api_key = os.getenv("LANGCHAIN_API_KEY")
    
    if langsmith_enabled and langsmith_api_key:
        logger.info("LangSmith tracing is enabled")
        project_name = os.getenv("LANGCHAIN_PROJECT", "irium-research")
        logger.info(f"LangSmith project: {project_name}")
        return True
    else:
        logger.info("LangSmith tracing is disabled")
        return False


def get_langsmith_url(run_id: Optional[str] = None) -> Optional[str]:
    """
    Get the LangSmith trace URL for a given run ID.
    
    Args:
        run_id: The LangSmith run ID
        
    Returns:
        URL to the trace if available, None otherwise
    """
    if not run_id:
        return None
    
    project_name = os.getenv("LANGCHAIN_PROJECT", "irium-research")
    # LangSmith trace URL format
    return f"https://smith.langchain.com/public/{project_name}/r/{run_id}"
