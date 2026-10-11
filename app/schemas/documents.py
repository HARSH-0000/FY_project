from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    """Document upload response."""
    document_id: int
    filename: str
    file_type: str
    file_size: int
    uploaded_at: datetime


class DocumentAnalysisRequest(BaseModel):
    """Document analysis request."""
    document_ids: List[int] = Field(..., min_items=1)
    query: str = Field(..., min_length=1, max_length=2000)


class DocumentAnalysisResponse(BaseModel):
    """Document analysis response."""
    analysis_id: int
    document_ids: List[int]
    query: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class DocumentInfo(BaseModel):
    """Document information."""
    id: int
    filename: str
    file_type: str
    file_size: int
    uploaded_at: datetime
