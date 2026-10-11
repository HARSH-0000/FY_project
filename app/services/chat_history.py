from sqlalchemy.orm import Session
from app.database.models import ChatSession, ChatMessage
from typing import List, Dict, Optional
from datetime import datetime


class ChatHistoryService:
    """Service for managing chat history."""
    
    def create_session(self, db: Session, user_id: int, title: str = None) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            user_id=user_id,
            title=title or "New Conversation"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    
    def get_user_sessions(self, db: Session, user_id: int, limit: int = 50) -> List[ChatSession]:
        """Get all chat sessions for a user."""
        return db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.updated_at.desc()).limit(limit).all()
    
    def get_session(self, db: Session, session_id: int, user_id: int) -> Optional[ChatSession]:
        """Get a specific chat session."""
        return db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        ).first()
    
    def add_message(
        self, 
        db: Session, 
        session_id: int, 
        role: str, 
        content: Dict,
        route: str = None,
        sources: List[Dict] = None
    ) -> ChatMessage:
        """Add a message to a chat session."""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            route=route,
            sources=sources
        )
        db.add(message)
        
        # Update session's updated_at timestamp
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.updated_at = datetime.utcnow()
            
            # Auto-generate title from first user message if not set
            if not session.title or session.title == "New Conversation":
                if role == "user" and isinstance(content, str):
                    session.title = content[:50] + ("..." if len(content) > 50 else "")
                elif role == "user" and isinstance(content, dict):
                    # Handle structured content
                    text = str(content)
                    session.title = text[:50] + ("..." if len(text) > 50 else "")
        
        db.commit()
        db.refresh(message)
        return message
    
    def get_session_messages(
        self, 
        db: Session, 
        session_id: int, 
        user_id: int
    ) -> List[ChatMessage]:
        """Get all messages in a chat session."""
        session = self.get_session(db, session_id, user_id)
        if not session:
            return []
        
        return db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()
    
    def delete_session(self, db: Session, session_id: int, user_id: int) -> bool:
        """Delete a chat session."""
        session = self.get_session(db, session_id, user_id)
        if not session:
            return False
        
        db.delete(session)
        db.commit()
        return True
    
    def update_session_title(
        self, 
        db: Session, 
        session_id: int, 
        user_id: int, 
        title: str
    ) -> Optional[ChatSession]:
        """Update a chat session title."""
        session = self.get_session(db, session_id, user_id)
        if not session:
            return None
        
        session.title = title
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
        return session


# Global chat history service instance
chat_history_service = ChatHistoryService()
