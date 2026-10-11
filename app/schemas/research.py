from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from datetime import datetime


class RouteDecision(BaseModel):
    """Router decision output."""
    route: Literal["SIMPLE", "VERIFICATION", "COMPLEX"]
    reason: str
    requires_current_information: bool
    requires_external_search: bool
    requires_multiple_sources: bool
    requires_comparison: bool
    requires_multi_step_reasoning: bool


class ResearchRequest(BaseModel):
    """Research request input."""
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[int] = None  # Optional chat session ID for history
    bypass_cache: bool = False  # Set to True to force fresh computation and bypass cache


class ResearchResponse(BaseModel):
    """Research response output."""
    job_id: int
    query: str
    route: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ResearchResult(BaseModel):
    """Final research result."""
    answer: str
    evidence: List[dict] = []
    sources: List[dict] = []
    route: str
    confidence: Optional[float] = None
