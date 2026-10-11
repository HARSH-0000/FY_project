from app.services.llm import llm_service
from app.services.search import search_service

def __getattr__(name):
    if name == "research_service":
        from app.services.research import research_service
        return research_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["llm_service", "search_service", "research_service"]

