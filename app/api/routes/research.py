from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from app.schemas.research import ResearchRequest
from app.services.research import research_service
from app.services.chat_history import chat_history_service
from app.services.anonymous_chat_db import anonymous_chat_db_service
from app.services.conversation_service import conversation_service
from app.services.query_resolver import query_resolver, QueryIntent
from app.services.auth import decode_access_token, get_user_by_id
from app.services.pii_detector import pii_service
from app.services.query_validator import query_validator
from app.database import get_db
from app.core import logger, settings
from typing import Optional, List, Dict, Any, AsyncGenerator
import json
import asyncio

router = APIRouter()


class PIIInspectRequest(BaseModel):
    text: str
    policy: Optional[str] = None


def log_request_lifecycle(
    stage: str,
    conversation_id: Optional[str],
    original_query: str,
    history_available: bool,
    history_count: int,
    resolved_query: Optional[str],
    intent: Optional[str],
    domain: Optional[str],
    validation_outcome: Optional[str],
    selected_route: Optional[str] = None,
    clarification_outcome: Optional[str] = None
):
    """Structured request lifecycle logging for observability and debugging."""
    sanitized_original = pii_service.sanitize_for_logging(original_query[:100]) if original_query else ""
    sanitized_resolved = pii_service.sanitize_for_logging(resolved_query[:100]) if resolved_query else ""
    logger.info(
        f"[{stage}] "
        f"conversation_id={conversation_id or 'none'} | "
        f"original_query='{sanitized_original}' | "
        f"history_available={history_available} | "
        f"history_messages={history_count} | "
        f"resolved_query='{sanitized_resolved}' | "
        f"intent={intent or 'N/A'} | "
        f"domain={domain or 'N/A'} | "
        f"validation={validation_outcome or 'N/A'} | "
        f"route={selected_route or 'N/A'} | "
        f"clarification={clarification_outcome or 'N/A'}"
    )


def get_effective_conversation_history(
    request: ResearchRequest,
    user: Optional[Any],
    db: Session,
    conversation_id: Optional[str]
) -> List[Dict]:
    """Retrieve history prioritizing payload turns, then user session messages, then persistent conversation store."""
    if request.conversation_history and len(request.conversation_history) > 0:
        return request.conversation_history

    session_id = getattr(request, 'session_id', None)
    if session_id and user:
        db_messages = chat_history_service.get_session_messages(db, session_id, user.id)
        if db_messages:
            return [
                {
                    "role": m.role,
                    "content": m.content if isinstance(m.content, str) else str(m.content)
                }
                for m in db_messages
            ]

    if conversation_id and conversation_id != "default":
        return conversation_service.get_history(conversation_id)

    return []


def save_conversation_turns(
    conversation_id: Optional[str],
    original_query: str,
    result: Dict,
    user: Optional[Any],
    session_id: Optional[int],
    db: Session
):
    """Save user and assistant turns to conversation_service and database."""
    answer_text = ""
    ans_obj = result.get("answer")
    if isinstance(ans_obj, str):
        answer_text = ans_obj
    elif isinstance(ans_obj, dict):
        if "summary" in ans_obj and ans_obj["summary"]:
            answer_text = ans_obj["summary"]
        elif "sections" in ans_obj:
            sec_texts = [s.get("content", "") for s in ans_obj["sections"] if isinstance(s, dict)]
            answer_text = "\n".join(sec_texts)
        else:
            answer_text = str(ans_obj)

    if conversation_id and conversation_id != "default":
        conversation_service.add_turn(conversation_id, "user", original_query)
        if answer_text:
            conversation_service.add_turn(conversation_id, "assistant", answer_text)

    if user and session_id:
        try:
            chat_history_service.add_message(
                db=db,
                session_id=session_id,
                role="user",
                content=original_query
            )
            chat_history_service.add_message(
                db=db,
                session_id=session_id,
                role="assistant",
                content=result.get("answer", {}),
                route=result.get("route"),
                sources=result.get("sources", [])
            )
        except Exception as e:
            logger.warning(f"Failed to save authenticated chat message: {e}")


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


@router.post("/api/research/stream")
async def stream_research(
    request: ResearchRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Stream research results as they become available using Server-Sent Events (SSE).
    This provides a better user experience with immediate feedback.
    """
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE stream of research progress and results."""
        try:
            # Check authentication
            user = None
            if authorization and authorization.startswith('Bearer '):
                token = authorization.split(' ')[1]
                payload = decode_access_token(token)
                if payload:
                    user_id = payload.get('sub')
                    if user_id:
                        user = get_user_by_id(db, int(user_id))

            conversation_id = getattr(request, 'conversation_id', None) or "default"
            history = get_effective_conversation_history(request, user, db, conversation_id)

            # 1. Context-aware query resolution
            resolution = await query_resolver.resolve_query(
                request.query,
                conversation_history=history
            )

            # 2. Check if clarification is required
            if resolution.requires_clarification:
                clarification_msg = (
                    resolution.clarification_question or
                    "Could you please specify which financial, economic, or business topic you would like me to explain?"
                )
                log_request_lifecycle(
                    stage="CLARIFICATION_REQUIRED",
                    conversation_id=conversation_id,
                    original_query=request.query,
                    history_available=bool(history),
                    history_count=len(history),
                    resolved_query=resolution.resolved_query,
                    intent=resolution.intent.value,
                    domain="ambiguous",
                    validation_outcome="CLARIFICATION",
                    selected_route="CLARIFICATION",
                    clarification_outcome=clarification_msg
                )
                clarification_result = {
                    "answer": clarification_msg,
                    "original_query": request.query,
                    "resolved_query": resolution.resolved_query,
                    "evidence": [],
                    "sources": [],
                    "visualizations": [],
                    "route": "CLARIFICATION",
                    "requires_clarification": True,
                    "clarification_question": clarification_msg
                }
                yield f"data: {json.dumps({'type': 'chunk', 'text': clarification_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'result', 'data': clarification_result})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # 3. Domain validation on resolved query
            validation_result = await query_validator.validate_query(
                request.query,
                conversation_history=history,
                resolved_query=resolution.resolved_query
            )

            if not validation_result["is_valid"]:
                log_request_lifecycle(
                    stage="DOMAIN_VALIDATION_FAILED",
                    conversation_id=conversation_id,
                    original_query=request.query,
                    history_available=bool(history),
                    history_count=len(history),
                    resolved_query=resolution.resolved_query,
                    intent=resolution.intent.value,
                    domain=validation_result.get("category"),
                    validation_outcome="INVALID",
                    selected_route="REJECTED",
                    clarification_outcome="None"
                )
                error_message = (
                    f" **This query is outside IRIUM's scope**\n\n"
                    f"**Your query:** {validation_result['category']}\n\n"
                    f"**Why it was rejected:** {validation_result['reason']}\n\n"
                    f"---\n\n"
                    f"**IRIUM specializes in:**\n"
                    f"💰 Finance, banking, and investments\n"
                    f"💳 Fintech and digital payments\n"
                    f"📊 Accounting and financial analysis\n"
                    f"📈 Economics and monetary policy\n"
                    f"📉 Stock markets and trading\n"
                    f"🏢 Business strategy and corporate finance\n\n"
                    f"**Please rephrase your question** to financial domain."
                )
                
                yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
                return
            
            # 4. PII Detection on resolved query
            query_to_execute = resolution.resolved_query
            pii_result = None

            if settings.PII_DETECTION_ENABLED:
                pii_result = pii_service.inspect(query_to_execute, policy=settings.PII_POLICY)
                if pii_result.has_pii:
                    if settings.PII_POLICY == "BLOCK":
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Query contains sensitive information: {', '.join(pii_result.categories_detected)}'})}\n\n"
                        return
                    query_to_execute = pii_result.sanitized_text

            bypass = getattr(request, 'bypass_cache', False)
            user_id_val = int(user.id) if user else None
            session_id_val = getattr(request, 'session_id', None)

            # Queue for streaming tokens generated by the LLM
            chunk_queue: asyncio.Queue = asyncio.Queue()

            async def on_token_chunk(chunk: str):
                if chunk:
                    await chunk_queue.put(chunk)

            from app.services.llm import stream_chunk_callback
            cb_token = stream_chunk_callback.set(on_token_chunk)

            async def run_research_task():
                try:
                    return await research_service.execute_research(
                        query_to_execute,
                        bypass_cache=bypass,
                        user_id=user_id_val,
                        session_id=session_id_val,
                        conversation_id=conversation_id,
                        conversation_history=history,
                        original_query=request.query,
                        resolved_query=resolution.resolved_query
                    )
                finally:
                    await chunk_queue.put(None)

            try:
                research_task = asyncio.create_task(run_research_task())

                # Stream chunks incrementally to frontend as LLM produces them
                while True:
                    chunk = await chunk_queue.get()
                    if chunk is None:
                        break
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

                result = await research_task
            finally:
                stream_chunk_callback.reset(cb_token)

            # Attach PII audit metadata if needed
            if pii_result and pii_result.has_pii:
                result["pii_protection"] = {
                    "detected": True,
                    "categories": pii_result.categories_detected,
                    "policy": settings.PII_POLICY
                }

            result["original_query"] = request.query
            result["resolved_query"] = resolution.resolved_query

            # Save chat to PostgreSQL database (anonymous, no auth required)
            try:
                import uuid
                chat_id = f"chat-{uuid.uuid4().hex[:12]}"
                
                anonymous_chat_db_service.save_chat(
                    db=db,
                    chat_id=chat_id,
                    query=request.query,
                    response=result,
                    route=result.get("route", "SIMPLE"),
                    ip_address=None,
                    user_agent=None
                )
                
                result["chat_id"] = chat_id
            except Exception as db_error:
                logger.warning(f"Failed to save chat to database: {db_error}")

            # Save conversation turns for dialogue continuity and persistence
            save_conversation_turns(
                conversation_id=conversation_id,
                original_query=request.query,
                result=result,
                user=user,
                session_id=session_id_val,
                db=db
            )

            # Observability logging
            log_request_lifecycle(
                stage="RESEARCH_COMPLETED",
                conversation_id=conversation_id,
                original_query=request.query,
                history_available=bool(history),
                history_count=len(history),
                resolved_query=resolution.resolved_query,
                intent=resolution.intent.value,
                domain=validation_result.get("category"),
                validation_outcome="VALID",
                selected_route=result.get("route", "UNKNOWN"),
                clarification_outcome="None"
            )

            # Send final structured result with sources, visualizations, metadata
            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            # Always send proper error event and done to close the stream
            try:
                error_message = str(e)
                if "rate_limit" in error_message.lower() or "429" in error_message:
                    error_message = "Rate limit encountered. Please wait a moment and try again."
                yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as yield_error:
                logger.error(f"Failed to yield error message: {yield_error}")
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )


@router.post("/api/research")
async def create_research(request: ResearchRequest):
    """
    SIMPLIFIED VERSION - Execute research query directly.
    """
    try:
        logger.info(f"Research request received: {request.query[:50]}")
        
        # Direct execution - bypass all validation for now
        from app.services.research import research_service
        
        result = await research_service.execute_research(
            query=request.query,
            bypass_cache=False,
            user_id=None,
            session_id=None,
            conversation_id="default",
            conversation_history=[],
            original_query=request.query,
            resolved_query=request.query
        )
        
        logger.info(f"Research completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"RESEARCH FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Research failed: {str(e)}"
        )


@router.post("/api/research/ORIGINAL_BACKUP")
async def create_research_original(
    request: ResearchRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    ORIGINAL VERSION - TEMPORARILY DISABLED
    Execute research query with PII protection.
    Optionally saves to chat history if user is authenticated.
    """
    try:
        # Check if user is authenticated
        user = None
        if authorization and authorization.startswith('Bearer '):
            token = authorization.split(' ')[1]
            payload = decode_access_token(token)
            if payload:
                user_id = payload.get('sub')
                if user_id:
                    user = get_user_by_id(db, int(user_id))

        conversation_id = getattr(request, 'conversation_id', None) or "default"
        history = get_effective_conversation_history(request, user, db, conversation_id)

        # 1. Context-aware query resolution
        resolution = await query_resolver.resolve_query(
            request.query,
            conversation_history=history
        )

        # 2. Check if clarification is required
        if resolution.requires_clarification:
            clarification_msg = (
                resolution.clarification_question or
                "Could you please specify which financial, economic, or business topic you would like me to explain?"
            )
            log_request_lifecycle(
                stage="CLARIFICATION_REQUIRED",
                conversation_id=conversation_id,
                original_query=request.query,
                history_available=bool(history),
                history_count=len(history),
                resolved_query=resolution.resolved_query,
                intent=resolution.intent.value,
                domain="ambiguous",
                validation_outcome="CLARIFICATION",
                selected_route="CLARIFICATION",
                clarification_outcome=clarification_msg
            )
            return {
                "job_id": 0,
                "query": request.query,
                "original_query": request.query,
                "resolved_query": resolution.resolved_query,
                "route": "CLARIFICATION",
                "status": "completed",
                "result": {
                    "answer": clarification_msg,
                    "evidence": [],
                    "sources": [],
                    "visualizations": [],
                    "route": "CLARIFICATION",
                    "confidence": resolution.confidence
                },
                "answer": clarification_msg,
                "evidence": [],
                "sources": [],
                "visualizations": [],
                "requires_clarification": True,
                "clarification_question": clarification_msg,
                "created_at": datetime.utcnow(),
                "completed_at": datetime.utcnow()
            }

        # 3. Domain validation on resolved query
        validation_result = await query_validator.validate_query(
            request.query,
            conversation_history=history,
            resolved_query=resolution.resolved_query
        )

        if not validation_result["is_valid"]:
            log_request_lifecycle(
                stage="DOMAIN_VALIDATION_FAILED",
                conversation_id=conversation_id,
                original_query=request.query,
                history_available=bool(history),
                history_count=len(history),
                resolved_query=resolution.resolved_query,
                intent=resolution.intent.value,
                domain=validation_result.get("category"),
                validation_outcome="INVALID",
                selected_route="REJECTED",
                clarification_outcome="None"
            )
            error_message = (
                f"**This query is outside IRIUM's scope**\n\n"
                f"**Your query:** {validation_result['category']}\n\n"
                f"**Why it was rejected:** {validation_result['reason']}\n\n"
                f"---\n\n"
                f"**IRIUM specializes in:**\n"
                f"• Finance, banking, and investments\n"
                f"• Fintech and digital payments\n"
                f"• Accounting and financial analysis\n"
                f"• Economics and monetary policy\n"
                f"• Stock markets and trading\n"
                f"• Business strategy and corporate finance\n\n"
                f"**Please rephrase your question** to relate to one of these financial topics."
            )
            
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_QUERY_DOMAIN",
                    "message": error_message,
                    "category": validation_result["category"],
                    "reason": validation_result["reason"]
                }
            )
        
        # 4. PII Detection and Protection
        query_to_execute = resolution.resolved_query
        pii_result = None

        if settings.PII_DETECTION_ENABLED:
            pii_result = pii_service.inspect(query_to_execute, policy=settings.PII_POLICY)
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
        
        # 5. Execute research
        bypass = getattr(request, 'bypass_cache', False)
        user_id_val = int(user.id) if user else None
        session_id_val = getattr(request, 'session_id', None)
        result = await research_service.execute_research(
            query_to_execute,
            bypass_cache=bypass,
            user_id=user_id_val,
            session_id=session_id_val,
            conversation_id=conversation_id,
            conversation_history=history,
            original_query=request.query,
            resolved_query=resolution.resolved_query
        )
        
        # Attach PII audit metadata to response if PII was detected
        if pii_result and pii_result.has_pii:
            result["pii_protection"] = {
                "detected": True,
                "categories": pii_result.categories_detected,
                "policy": settings.PII_POLICY
            }

        result["original_query"] = request.query
        result["resolved_query"] = resolution.resolved_query
        
        # Save chat to PostgreSQL database (anonymous, no auth required)
        # TEMPORARILY DISABLED - May be causing 500 error with SQLite
        try:
            import uuid
            chat_id = f"chat-{uuid.uuid4().hex[:12]}"
            
            # # Save to PostgreSQL
            # anonymous_chat_db_service.save_chat(
            #     db=db,
            #     chat_id=chat_id,
            #     query=request.query,
            #     response=result,
            #     route=result.get("route", "SIMPLE"),
            #     ip_address=None,
            #     user_agent=None
            # )
            
            # Add chat_id to result for reference
            result["chat_id"] = chat_id
            logger.info(f"Chat ID generated (save disabled): {chat_id}")
            
        except Exception as db_error:
            logger.error(f"Failed to generate chat ID: {db_error}")
        
        # Save conversation turns
        save_conversation_turns(
            conversation_id=conversation_id,
            original_query=request.query,
            result=result,
            user=user,
            session_id=session_id_val,
            db=db
        )

        # Observability logging
        log_request_lifecycle(
            stage="RESEARCH_COMPLETED",
            conversation_id=conversation_id,
            original_query=request.query,
            history_available=bool(history),
            history_count=len(history),
            resolved_query=resolution.resolved_query,
            intent=resolution.intent.value,
            domain=validation_result.get("category"),
            validation_outcome="VALID",
            selected_route=result.get("route", "UNKNOWN"),
            clarification_outcome="None"
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"RESEARCH FAILED: {e}")
        traceback.print_exc()
        raise


@router.post("/debug")
async def debug_research(request: ResearchRequest):
    """
    Debug endpoint that returns detailed execution information.
    Useful for diagnosing "Insufficient information" issues.
    """
    try:
        logger.info(f"DEBUG: Starting research for query: {request.query}")
        
        from app.core.budget import start_request_budget
        start_request_budget()
        
        result = await research_service.execute_research(
            request.query,
            bypass_cache=request.bypass_cache,
            user_id=None,
            session_id=None
        )
        
        # Return detailed debug information
        return {
            "query": request.query,
            "route": result.get("route", "unknown"),
            "answer_available": bool(result.get("answer")),
            "answer_type": type(result.get("answer")).__name__ if result.get("answer") else "None",
            "answer_preview": str(result.get("answer", ""))[:200],
            "evidence_count": len(result.get("evidence", [])),
            "sources_count": len(result.get("sources", [])),
            "critique_score": result.get("critique", {}).get("quality_score"),
            "execution_time_ms": result.get("duration_ms", 0),
            "trace_id": result.get("trace_id", ""),
            "error": result.get("error"),
            "debug_details": {
                "has_evidence": bool(result.get("evidence")),
                "evidence_preview": [ev.get("claim", "")[:100] for ev in result.get("evidence", [])[:3]],
                "source_urls": [s.get("url", "") for s in result.get("sources", [])[:3]]
            }
        }
        
    except Exception as e:
        logger.error(f"Debug research failed: {e}")
        return {
            "error": str(e),
            "query": request.query,
            "debug_error": True
        }


@router.post("/clear-cache")
async def clear_research_cache():
    """
    Clear all cached research results.
    Useful when bad responses get cached.
    """
    try:
        from app.services.cache import cache_service
        
        # Clear all cache entries matching research pattern
        cleared_count = await cache_service.clear("irium:research:*")
        
        logger.info(f"Cleared {cleared_count} cached research results")
        
        return {
            "success": True,
            "message": f"Cleared {cleared_count} cached research results",
            "cleared_count": cleared_count
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/chat-history")
async def get_chat_history(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get recent chat history from PostgreSQL database.
    """
    try:
        chats = anonymous_chat_db_service.get_recent_chats(db, limit=limit, offset=offset)
        stats = anonymous_chat_db_service.get_chat_stats(db)
        
        return {
            "total_chats": stats["total_chats"],
            "stats": stats,
            "chats": [
                {
                    "chat_id": chat.chat_id,
                    "query": chat.query,
                    "route": chat.route,
                    "created_at": chat.created_at.isoformat() if chat.created_at else None,
                    "duration_ms": chat.duration_ms,
                    "trace_id": chat.trace_id,
                    "evidence_count": len(chat.evidence) if chat.evidence else 0,
                    "sources_count": len(chat.sources) if chat.sources else 0
                }
                for chat in chats
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-history/{chat_id}")
async def get_chat_by_id(chat_id: str, db: Session = Depends(get_db)):
    """
    Get a specific chat by ID from PostgreSQL database.
    """
    try:
        chat = anonymous_chat_db_service.get_chat_by_id(db, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return anonymous_chat_db_service.export_to_dict(chat)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-history/search/{search_term}")
async def search_chats(
    search_term: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Search chats by query text.
    """
    try:
        chats = anonymous_chat_db_service.search_chats(db, search_term, limit=limit)
        
        return {
            "search_term": search_term,
            "results_count": len(chats),
            "chats": [anonymous_chat_db_service.export_to_dict(chat) for chat in chats]
        }
    except Exception as e:
        logger.error(f"Failed to search chats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-stats")
async def get_chat_stats(db: Session = Depends(get_db)):
    """
    Get statistics about stored chats.
    """
    try:
        return anonymous_chat_db_service.get_chat_stats(db)
    except Exception as e:
        logger.error(f"Failed to get chat stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-all-chats")
async def export_all_chats(db: Session = Depends(get_db)):
    """
    Export all chats from PostgreSQL to a JSON file.
    """
    try:
        import json
        from pathlib import Path
        
        # Get all chats
        chats = anonymous_chat_db_service.get_recent_chats(db, limit=10000)
        
        # Convert to dict
        export_data = {
            "project": "Irium MVP - PostgreSQL Export",
            "exported_at": datetime.utcnow().isoformat(),
            "total_chats": len(chats),
            "chats": [anonymous_chat_db_service.export_to_dict(chat) for chat in chats]
        }
        
        # Save to file
        export_dir = Path("data/chat_exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        filepath = export_dir / "postgresql_export.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(chats)} chats from PostgreSQL to {filepath}")
        
        return {
            "success": True,
            "message": f"Exported {len(chats)} chats successfully",
            "file_path": str(filepath),
            "total_chats": len(chats)
        }
    except Exception as e:
        logger.error(f"Failed to export chats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
