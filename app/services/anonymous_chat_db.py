"""
Service for storing anonymous chats in PostgreSQL database.
"""
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database.models import AnonymousChat
from app.core import logger


class AnonymousChatDBService:
    """Service for managing anonymous chats in PostgreSQL."""
    
    def save_chat(
        self,
        db: Session,
        chat_id: str,
        query: str,
        response: Dict,
        route: str = "SIMPLE",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AnonymousChat:
        """
        Save a chat to PostgreSQL database.
        
        Args:
            db: Database session
            chat_id: Unique chat identifier
            query: User query
            response: Research response
            route: Route used (SIMPLE, VERIFICATION, COMPLEX)
            ip_address: Optional IP address
            user_agent: Optional browser user agent
            
        Returns:
            Created AnonymousChat record
        """
        try:
            chat_record = AnonymousChat(
                chat_id=chat_id,
                query=query,
                route=route,
                answer=response.get("answer", {}),
                evidence=response.get("evidence", []),
                sources=response.get("sources", []),
                trace_id=response.get("trace_id"),
                duration_ms=response.get("duration_ms"),
                ip_address=ip_address,
                user_agent=user_agent,
                pii_detected=response.get("pii_protection", {}).get("detected", False),
                cached=response.get("cached", False)
            )
            
            db.add(chat_record)
            db.commit()
            db.refresh(chat_record)
            
            logger.info(f"✅ Chat saved to PostgreSQL: {chat_id} (ID: {chat_record.id})")
            return chat_record
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to save chat {chat_id} to PostgreSQL: {e}")
            raise
    
    def get_chat_by_id(self, db: Session, chat_id: str) -> Optional[AnonymousChat]:
        """
        Get a specific chat by ID.
        
        Args:
            db: Database session
            chat_id: Unique chat identifier
            
        Returns:
            AnonymousChat record or None
        """
        try:
            return db.query(AnonymousChat).filter(
                AnonymousChat.chat_id == chat_id
            ).first()
        except Exception as e:
            logger.error(f"Failed to get chat {chat_id}: {e}")
            return None
    
    def get_recent_chats(
        self,
        db: Session,
        limit: int = 50,
        offset: int = 0
    ) -> List[AnonymousChat]:
        """
        Get recent chats ordered by creation date.
        
        Args:
            db: Database session
            limit: Maximum number of chats to return
            offset: Number of chats to skip
            
        Returns:
            List of AnonymousChat records
        """
        try:
            return db.query(AnonymousChat).order_by(
                desc(AnonymousChat.created_at)
            ).offset(offset).limit(limit).all()
        except Exception as e:
            logger.error(f"Failed to get recent chats: {e}")
            return []
    
    def get_chats_by_route(
        self,
        db: Session,
        route: str,
        limit: int = 50
    ) -> List[AnonymousChat]:
        """
        Get chats by route type.
        
        Args:
            db: Database session
            route: Route type (SIMPLE, VERIFICATION, COMPLEX)
            limit: Maximum number of chats
            
        Returns:
            List of AnonymousChat records
        """
        try:
            return db.query(AnonymousChat).filter(
                AnonymousChat.route == route
            ).order_by(
                desc(AnonymousChat.created_at)
            ).limit(limit).all()
        except Exception as e:
            logger.error(f"Failed to get chats by route {route}: {e}")
            return []
    
    def search_chats(
        self,
        db: Session,
        search_term: str,
        limit: int = 50
    ) -> List[AnonymousChat]:
        """
        Search chats by query text.
        
        Args:
            db: Database session
            search_term: Text to search for in queries
            limit: Maximum number of results
            
        Returns:
            List of matching AnonymousChat records
        """
        try:
            return db.query(AnonymousChat).filter(
                AnonymousChat.query.ilike(f"%{search_term}%")
            ).order_by(
                desc(AnonymousChat.created_at)
            ).limit(limit).all()
        except Exception as e:
            logger.error(f"Failed to search chats: {e}")
            return []
    
    def get_chat_stats(self, db: Session) -> Dict:
        """
        Get statistics about stored chats.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with statistics
        """
        try:
            from sqlalchemy import func
            
            total_chats = db.query(func.count(AnonymousChat.id)).scalar()
            
            route_counts = db.query(
                AnonymousChat.route,
                func.count(AnonymousChat.id)
            ).group_by(AnonymousChat.route).all()
            
            avg_duration = db.query(
                func.avg(AnonymousChat.duration_ms)
            ).scalar()
            
            pii_count = db.query(
                func.count(AnonymousChat.id)
            ).filter(
                AnonymousChat.pii_detected == True
            ).scalar()
            
            return {
                "total_chats": total_chats or 0,
                "routes": {route: count for route, count in route_counts},
                "avg_duration_ms": float(avg_duration) if avg_duration else 0,
                "pii_detected_count": pii_count or 0
            }
        except Exception as e:
            logger.error(f"Failed to get chat stats: {e}")
            return {
                "total_chats": 0,
                "routes": {},
                "avg_duration_ms": 0,
                "pii_detected_count": 0,
                "error": str(e)
            }
    
    def delete_old_chats(
        self,
        db: Session,
        days_old: int = 30
    ) -> int:
        """
        Delete chats older than specified days.
        
        Args:
            db: Database session
            days_old: Delete chats older than this many days
            
        Returns:
            Number of chats deleted
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            deleted_count = db.query(AnonymousChat).filter(
                AnonymousChat.created_at < cutoff_date
            ).delete()
            
            db.commit()
            logger.info(f"Deleted {deleted_count} chats older than {days_old} days")
            return deleted_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete old chats: {e}")
            return 0
    
    def export_to_dict(self, chat: AnonymousChat) -> Dict:
        """
        Convert AnonymousChat record to dictionary.
        
        Args:
            chat: AnonymousChat record
            
        Returns:
            Dictionary representation
        """
        return {
            "id": chat.id,
            "chat_id": chat.chat_id,
            "query": chat.query,
            "route": chat.route,
            "answer": chat.answer,
            "evidence": chat.evidence,
            "sources": chat.sources,
            "trace_id": chat.trace_id,
            "duration_ms": chat.duration_ms,
            "created_at": chat.created_at.isoformat() if chat.created_at else None,
            "pii_detected": chat.pii_detected,
            "cached": chat.cached
        }


# Global service instance
anonymous_chat_db_service = AnonymousChatDBService()
