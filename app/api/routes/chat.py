from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.services.chat_history import chat_history_service
from app.api.routes.auth import get_current_user
from typing import List, Optional, Dict
from datetime import datetime

router = APIRouter()


# Pydantic models
class ChatSessionCreate(BaseModel):
    title: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: Dict
    route: Optional[str]
    sources: Optional[List[Dict]]
    created_at: str


class ChatSessionDetail(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    messages: List[ChatMessageResponse]


@router.post("/api/chat/sessions", response_model=ChatSessionResponse)
async def create_session(
    session_data: ChatSessionCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session."""
    session = chat_history_service.create_session(
        db=db,
        user_id=current_user.id,
        title=session_data.title
    )
    
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "message_count": 0
    }


@router.get("/api/chat/sessions", response_model=List[ChatSessionResponse])
async def get_sessions(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50
):
    """Get all chat sessions for current user."""
    sessions = chat_history_service.get_user_sessions(
        db=db,
        user_id=current_user.id,
        limit=limit
    )
    
    return [
        {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": len(session.messages)
        }
        for session in sessions
    ]


@router.get("/api/chat/sessions/{session_id}", response_model=ChatSessionDetail)
async def get_session(
    session_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific chat session with all messages."""
    session = chat_history_service.get_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = chat_history_service.get_session_messages(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )
    
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "route": msg.route,
                "sources": msg.sources,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ]
    }


@router.delete("/api/chat/sessions/{session_id}")
async def delete_session(
    session_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat session."""
    success = chat_history_service.delete_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"message": "Session deleted successfully"}


@router.put("/api/chat/sessions/{session_id}/title")
async def update_session_title(
    session_id: int,
    title: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a chat session title."""
    session = chat_history_service.update_session_title(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        title=title
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"message": "Title updated successfully", "title": session.title}
