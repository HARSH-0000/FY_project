"""
Documents API Route
Handles file upload, validation, ingestion, grounded QA, and conversation follow-ups.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
import json

from app.core import logger, settings
from app.documents.validator import document_validator, DocumentValidationError
from app.services.document_service import document_service
from app.services.document_store import document_store
from app.agents.document_analysis import document_analysis_agent
from app.services.pii_detector import pii_service

router = APIRouter()


@router.post("/api/documents/analyze")
async def analyze_documents(
    query: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    session_id: Optional[str] = Form(None),
    document_id: Optional[str] = Form(None),
    conversation_history: Optional[str] = Form(None)
):
    """
    Analyze uploaded documents or answer follow-up questions for a session document.
    """
    try:
        # PII Protection for query
        if settings.PII_DETECTION_ENABLED:
            query, _ = pii_service.redact(query, policy=settings.PII_POLICY)

        # Parse conversation history if provided
        history_list = []
        if conversation_history:
            try:
                history_list = json.loads(conversation_history)
            except Exception:
                history_list = []

        # Case 1: New file(s) uploaded
        if files and len(files) > 0 and files[0].filename:
            logger.info(f"Processing upload of {len(files)} file(s) for query: {query[:50]}...")
            ingested_docs = []

            for file in files:
                content = await file.read()
                try:
                    ingested = await document_service.ingest_file(
                        filename=file.filename,
                        content=content,
                        session_id=session_id
                    )
                    ingested_docs.append(ingested)
                except DocumentValidationError as ve:
                    logger.warning(f"Validation failed for {file.filename}: {ve.message}")
                    raise HTTPException(status_code=400, detail=ve.message)
                except Exception as e:
                    logger.error(f"Failed to ingest {file.filename}: {e}", exc_info=True)
                    raise HTTPException(status_code=400, detail=f"Failed to process {file.filename}: {str(e)}")

            if not ingested_docs:
                raise HTTPException(status_code=400, detail="No valid documents were processed.")

            # Retrieve context for query
            # Retrieve context for query (optimized top_k=4 to avoid token limits)
            doc_id = ingested_docs[0]["document_id"] if len(ingested_docs) == 1 else None
            retrieval = document_service.retrieve_context(
                query=query,
                session_id=session_id,
                document_id=doc_id,
                top_k=4
            )

            # Analyze with agent
            result = await document_analysis_agent.analyze(
                query=query,
                documents=ingested_docs,
                retrieved_context=retrieval["context_text"],
                source_pages=retrieval["source_pages"],
                conversation_history=history_list
            )

            return {
                "answer": result.get("answer", ""),
                "documents": [d["filename"] for d in ingested_docs],
                "document_ids": [d["document_id"] for d in ingested_docs],
                "primary_document_id": ingested_docs[0]["document_id"],
                "source_pages": result.get("source_pages", []),
                "metadata": {
                    "document_count": len(ingested_docs),
                    "page_count": sum(d.get("page_count", 1) for d in ingested_docs),
                    "query": query,
                    "session_id": session_id,
                    "processed_at": datetime.utcnow().isoformat()
                }
            }

        # Case 2: Follow-up question about an existing document in this session
        elif session_id or document_id:
            logger.info(f"Processing document follow-up query for session={session_id}, doc={document_id}")
            
            # Check if active documents exist
            session_docs = []
            if session_id:
                session_docs = document_store.get_session_documents(session_id)
            elif document_id:
                doc = document_store.get_document(document_id)
                if doc:
                    session_docs = [doc]

            if not session_docs:
                raise HTTPException(
                    status_code=404,
                    detail="No uploaded document found in this conversation. Please upload a PDF or image first."
                )

            # Retrieve relevant chunks for follow-up query (top_k=4)
            retrieval = document_service.retrieve_context(
                query=query,
                session_id=session_id,
                document_id=document_id or (session_docs[0]["document_id"] if session_docs else None),
                top_k=4
            )

            # Analyze grounded in the retrieved document context and previous conversation turns
            result = await document_analysis_agent.analyze(
                query=query,
                documents=None,
                retrieved_context=retrieval["context_text"],
                source_pages=retrieval["source_pages"],
                conversation_history=history_list
            )

            doc_names = [d["filename"] for d in session_docs]
            is_general = result.get("is_general_query", False)
            return {
                "answer": result.get("answer", ""),
                "documents": [] if is_general else doc_names,
                "document_ids": [d["document_id"] for d in session_docs],
                "source_pages": result.get("source_pages", []),
                "metadata": {
                    "is_follow_up": True,
                    "is_general_query": is_general,
                    "document_count": len(session_docs),
                    "query": query,
                    "session_id": session_id,
                    "processed_at": datetime.utcnow().isoformat()
                }
            }

        else:
            raise HTTPException(
                status_code=400,
                detail="Please select a document to upload or specify a conversation session."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document analysis endpoint failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/documents/session/{session_id}")
async def get_session_documents(session_id: str):
    """Get active documents associated with a chat session."""
    docs = document_store.get_session_documents(session_id)
    return {
        "session_id": session_id,
        "document_count": len(docs),
        "documents": docs
    }


@router.delete("/api/documents/session/{session_id}")
async def detach_session_documents(session_id: str):
    """Detach documents from a chat session."""
    success = document_store.detach_session_documents(session_id)
    return {
        "session_id": session_id,
        "detached": success,
        "message": "Documents detached from session."
    }
