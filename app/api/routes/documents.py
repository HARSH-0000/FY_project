from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.documents.parser import document_parser
from app.agents.document_analysis import document_analysis_agent
from app.core import logger, settings
from datetime import datetime
from typing import List
import os
import tempfile

router = APIRouter()


@router.post("/api/documents/analyze")
async def analyze_documents(
    query: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Analyze uploaded documents directly (no database required for MVP).
    Accept files and query, process immediately, return results.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        logger.info(f"Processing {len(files)} document(s) with query: {query}")
        
        # Process each file
        documents = []
        temp_files = []
        
        for file in files:
            # Validate file type
            file_ext = file.filename.split('.')[-1].lower()
            allowed_types = settings.ALLOWED_FILE_TYPES.split(',')
            
            if file_ext not in allowed_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{file_ext}' not allowed. Allowed: {allowed_types}"
                )
            
            # Check file size
            content = await file.read()
            file_size = len(content)
            
            max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            if file_size > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' too large. Maximum: {settings.MAX_UPLOAD_SIZE_MB}MB"
                )
            
            # Save to temporary file for parsing
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}') as tmp:
                tmp.write(content)
                temp_path = tmp.name
                temp_files.append(temp_path)
            
            logger.info(f"Parsing file: {file.filename}")
            
            # Parse document
            try:
                parsed = document_parser.parse(temp_path, file_ext)
                
                documents.append({
                    "filename": file.filename,
                    "text_content": parsed["text_content"],
                    "metadata": parsed["metadata"]
                })
                
                logger.info(f"Successfully parsed: {file.filename}")
                
            except Exception as e:
                logger.error(f"Failed to parse {file.filename}: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse {file.filename}: {str(e)}"
                )
        
        if not documents:
            raise HTTPException(status_code=400, detail="No valid documents to analyze")
        
        # PII Protection for uploaded documents and query
        if settings.PII_DETECTION_ENABLED:
            from app.services.pii_detector import pii_service
            query, _ = pii_service.redact(query, policy=settings.PII_POLICY)
            for doc in documents:
                if "text_content" in doc and doc["text_content"]:
                    doc["text_content"], _ = pii_service.redact(doc["text_content"], policy="REDACT")
        
        # Execute analysis
        logger.info(f"Analyzing {len(documents)} document(s)...")
        result = await document_analysis_agent.analyze(query, documents)
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        
        logger.info(f"Document analysis completed successfully")
        
        # Return result in format expected by frontend
        return {
            "answer": result.get("answer", ""),
            "documents": [doc["filename"] for doc in documents],
            "evidence": result.get("evidence", []),
            "metadata": {
                "document_count": len(documents),
                "query": query,
                "processed_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
