from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict
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


class ConversationTurn(BaseModel):
    """A single turn in the conversation."""
    role: Literal["user", "assistant"]
    content: str


class ResearchRequest(BaseModel):
    """Research request input."""
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None  # Conversation identifier for multi-turn context
    conversation_history: Optional[List[Dict]] = None  # Previous turns for context
    session_id: Optional[int] = None  # Optional authenticated chat session ID
    bypass_cache: bool = False  # Set to True to force fresh computation and bypass cache


class ResearchResponse(BaseModel):
    """Research response output."""
    job_id: int
    query: str
    original_query: Optional[str] = None
    resolved_query: Optional[str] = None
    route: str
    status: str
    result: Optional[dict] = None
    visualizations: List[dict] = Field(default_factory=list)
    error: Optional[str] = None
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ResearchResult(BaseModel):
    """Final research result."""
    answer: str
    original_query: Optional[str] = None
    resolved_query: Optional[str] = None
    evidence: List[dict] = []
    sources: List[dict] = []
    visualizations: List[dict] = Field(default_factory=list)
    route: str
    confidence: Optional[float] = None
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
