"""
Persistent Memory API routes for preferences, session context, and research history.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from app.services.memory import memory_service
from app.services.auth import decode_access_token

router = APIRouter()


class PreferenceRequest(BaseModel):
    report_structure: Optional[str] = Field(None, description="e.g. executive_summary, detailed_tables, bulleted_risks")
    level_of_detail: Optional[str] = Field(None, description="e.g. concise, comprehensive, deep_dive")
    financial_analysis_format: Optional[str] = Field(None, description="e.g. valuation_centric, risk_centric, regulatory_centric")
    custom_preferences: Optional[Dict[str, Any]] = None


class SessionContextRequest(BaseModel):
    company: Optional[str] = None
    objective: Optional[str] = None
    follow_up: Optional[str] = None
    earlier_reference: Optional[str] = None


class DeleteMemoryRequest(BaseModel):
    category: str
    key: str
    session_id: Optional[int] = None


def get_current_user_id_optional(authorization: Optional[str] = Header(None)) -> Optional[int]:
    """Extract authenticated user ID if bearer token present."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            try:
                return int(payload["sub"])
            except ValueError:
                return None
    return None


@router.get("/api/memory/preferences")
async def get_preferences(
    user_id: Optional[int] = Depends(get_current_user_id_optional)
):
    """Retrieve saved preferences for current user (or default user_id=1 for guest testing)."""
    uid = user_id or 1
    return {
        "user_id": uid,
        "preferences": memory_service.get_preferences(uid)
    }


@router.post("/api/memory/preferences")
async def save_preferences(
    request: PreferenceRequest,
    user_id: Optional[int] = Depends(get_current_user_id_optional)
):
    """Save or update user preferences."""
    uid = user_id or 1
    if request.report_structure:
        memory_service.save_preference(uid, "report_structure", request.report_structure)
    if request.level_of_detail:
        memory_service.save_preference(uid, "level_of_detail", request.level_of_detail)
    if request.financial_analysis_format:
        memory_service.save_preference(uid, "financial_analysis_format", request.financial_analysis_format)
    if request.custom_preferences:
        for k, v in request.custom_preferences.items():
            memory_service.save_preference(uid, k, v)

    return {
        "status": "success",
        "user_id": uid,
        "preferences": memory_service.get_preferences(uid)
    }


@router.get("/api/memory/session/{session_id}")
async def get_session_context(session_id: int):
    """Retrieve context (discussed companies, objectives) for a session."""
    return {
        "session_id": session_id,
        "context": memory_service.get_session_context(session_id)
    }


@router.post("/api/memory/session/{session_id}")
async def update_session_context(session_id: int, request: SessionContextRequest):
    """Update context for a research session."""
    memory_service.update_session_context(
        session_id=session_id,
        company=request.company,
        objective=request.objective,
        follow_up=request.follow_up,
        earlier_reference=request.earlier_reference
    )
    return {
        "status": "success",
        "session_id": session_id,
        "context": memory_service.get_session_context(session_id)
    }


@router.get("/api/memory/history")
async def get_history(
    session_id: Optional[int] = None,
    limit: int = 10,
    user_id: Optional[int] = Depends(get_current_user_id_optional)
):
    """Retrieve persistent research history."""
    return {
        "history": memory_service.get_research_history(user_id=user_id, session_id=session_id, limit=limit)
    }


@router.delete("/api/memory")
async def delete_memory(
    request: DeleteMemoryRequest,
    user_id: Optional[int] = Depends(get_current_user_id_optional)
):
    """Delete a specific stored memory."""
    deleted = memory_service.delete_memory(
        category=request.category,
        key=request.key,
        user_id=user_id or 1,
        session_id=request.session_id
    )
    return {"status": "deleted" if deleted else "not_found"}


@router.post("/api/memory/clear")
async def clear_all_memories(
    session_id: Optional[int] = None,
    user_id: Optional[int] = Depends(get_current_user_id_optional)
):
    """Clear memory within the current user or session scope."""
    count = memory_service.clear_all(user_id=user_id, session_id=session_id)
    return {"status": "cleared", "records_removed": count}
