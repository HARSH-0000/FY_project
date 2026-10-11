from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class Evidence(BaseModel):
    """Evidence model."""
    claim: str = Field(..., description="The claim being made")
    source_title: str = Field(..., description="Title of the source")
    source_url: str = Field(..., description="URL of the source")
    source_name: Optional[str] = Field(None, description="Name of the source (e.g., company, organization)")
    evidence_text: str = Field(..., description="Extracted text that supports the claim")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")


class Source(BaseModel):
    """Source model."""
    title: str
    url: str
    name: Optional[str] = None
    relevance_score: Optional[float] = None
