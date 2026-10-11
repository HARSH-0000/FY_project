from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.schemas.research import ResearchRequest
from app.services.research import research_service
from app.services.chat_history import chat_history_service
from app.services.auth import decode_access_token, get_user_by_id
from app.services.pii_detector import pii_service
from app.database import get_db
from app.core import logger, settings
from typing import Optional, List

router = APIRouter()


class PIIInspectRequest(BaseModel):
    text: str
    policy: Optional[str] = None


@router.post("/api/pii/inspect")
async def inspect_pii(request: PIIInspectRequest):
    """Inspect text for PII without executing research."""
    policy = request.policy or settings.PII_POLICY
    result = pii_service.inspect(request.text, policy=policy)
    return {
        "has_pii": result.has_pii,
        "categories": result.categories_detected,
        "sanitized_text": result.sanitized_text,
        "policy": result.policy_applied,
        "entity_count": len(result.entities)
    }


@router.post("/api/research")
async def create_research(
    request: ResearchRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Execute research query with PII protection.
    Optionally saves to chat history if user is authenticated.
    """
    try:
        # PII Detection and Protection
        query_to_execute = request.query
        pii_result = None

        if settings.PII_DETECTION_ENABLED:
            pii_result = pii_service.inspect(request.query, policy=settings.PII_POLICY)
            if pii_result.has_pii:
                logger.info(
                    f"PII detected in incoming query: categories={pii_result.categories_detected}, "
                    f"policy={settings.PII_POLICY}"
                )
                if settings.PII_POLICY == "BLOCK":
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "PII_DETECTED",
                            "message": (
                                f"Query contains sensitive personal information: "
                                f"{', '.join(pii_result.categories_detected)}. "
                                f"Please remove personal identifiers to protect your privacy."
                            ),
                            "categories": pii_result.categories_detected
                        }
                    )
                query_to_execute = pii_result.sanitized_text

        logger.info(f"Processing research query: {pii_service.sanitize_for_logging(query_to_execute)}")
        
        # Check if user is authenticated
        user = None
        session_id = getattr(request, 'session_id', None)
        
        if authorization and authorization.startswith('Bearer '):
            token = authorization.split(' ')[1]
            payload = decode_access_token(token)
            if payload:
                user_id = payload.get('sub')
                if user_id:
                    user = get_user_by_id(db, int(user_id))
        
        # Execute research directly (synchronous for MVP)
        bypass = getattr(request, 'bypass_cache', False)
        user_id_val = int(user.id) if user else None
        session_id_val = getattr(request, 'session_id', None)
        result = await research_service.execute_research(
            query_to_execute,
            bypass_cache=bypass,
            user_id=user_id_val,
            session_id=session_id_val
        )
        
        # Attach PII audit metadata to response if PII was detected
        if pii_result and pii_result.has_pii:
            result["pii_protection"] = {
                "detected": True,
                "categories": pii_result.categories_detected,
                "policy": settings.PII_POLICY
            }
        
        # Save to chat history if user is authenticated
        if user and session_id:
            # Add user message
            chat_history_service.add_message(
                db=db,
                session_id=session_id,
                role="user",
                content=request.query
            )
            
            # Add assistant message
            chat_history_service.add_message(
                db=db,
                session_id=session_id,
                role="assistant",
                content=result.get("answer", {}),
                route=result.get("route"),
                sources=result.get("sources", [])
            )
        
        logger.info(f"Research completed for query: {request.query}")
        
        return result
        
    except Exception as e:
        import traceback

        logger.error("RESEARCH FAILED")
        traceback.print_exc()

        raise
