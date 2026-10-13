"""
Document Service for Irium Document Intelligence.
Coordinates document validation, parsing, semantic chunking, SQLite/FTS5 persistence,
and retrieval for grounded question answering.
"""

import uuid
import os
import re
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core import logger, settings
from app.documents.validator import document_validator, DocumentValidationError
from app.documents.parser import document_parser
from app.services.document_store import document_store


class DocumentService:
    """Coordinates file ingestion, chunking, storage, and contextual retrieval."""

    def __init__(self):
        self.chunk_size = 900
        self.chunk_overlap = 150

    async def ingest_file(
        self,
        filename: str,
        content: bytes,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate, parse, chunk, and index an uploaded document.
        
        Args:
            filename: Original filename
            content: Raw file bytes
            session_id: Optional conversation/session ID
            user_id: Optional user identifier
            
        Returns:
            Dict containing ingestion summary, document_id, page_count, and text.
        """
        # 1. Validate file
        val_info = document_validator.validate_file(filename, content)
        file_ext = val_info["file_ext"]
        page_count = val_info["page_count"]

        # 2. Generate unique document ID
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        temp_path = None

        try:
            # 3. Save to temporary file for parser
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                tmp.write(content)
                temp_path = tmp.name

            # 4. Parse document
            logger.info(f"Ingesting file {filename} (id: {document_id}, session: {session_id})")
            parsed = document_parser.parse(temp_path, file_ext)

            full_text = parsed.get("text_content", "")
            pages_data = parsed.get("pages", [])
            metadata = parsed.get("metadata", {})

            # Ensure page count matches parsed if available
            actual_pages = metadata.get("total_pages", page_count or 1)

            # 5. Semantic Chunking
            chunks = self._create_chunks(document_id, filename, pages_data, full_text)

            # 6. Save in SQLite document store
            document_store.save_document(
                document_id=document_id,
                filename=filename,
                file_type=file_ext,
                page_count=actual_pages,
                size_bytes=len(content),
                full_text=full_text,
                metadata=metadata,
                session_id=session_id,
                user_id=user_id
            )

            # 7. Save and index chunks for FTS5 retrieval
            document_store.save_chunks(
                document_id=document_id,
                chunks=chunks,
                session_id=session_id,
                filename=filename
            )

            logger.info(
                f"Ingestion complete: {filename} ({document_id}) -> "
                f"{actual_pages} pages, {len(chunks)} chunks indexed"
            )

            return {
                "document_id": document_id,
                "filename": filename,
                "file_type": file_ext,
                "page_count": actual_pages,
                "size_bytes": len(content),
                "chunks_count": len(chunks),
                "text_content": full_text,
                "metadata": metadata
            }

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    def _create_chunks(
        self,
        document_id: str,
        filename: str,
        pages_data: List[Dict[str, Any]],
        full_text: str
    ) -> List[Dict[str, Any]]:
        """Split document into semantic chunks with page numbers and metadata."""
        chunks = []
        chunk_counter = 0

        if pages_data:
            for page_info in pages_data:
                page_num = page_info.get("page_number", 1)
                page_text = page_info.get("text", "").strip()

                if not page_text:
                    continue

                # If page is short, keep as single chunk
                if len(page_text) <= self.chunk_size:
                    chunks.append({
                        "chunk_id": f"{document_id}_p{page_num}_c0",
                        "document_id": document_id,
                        "filename": filename,
                        "page_number": page_num,
                        "chunk_index": 0,
                        "content": page_text,
                        "metadata": {
                            "page_number": page_num,
                            "filename": filename,
                            "is_image": page_info.get("is_image", False)
                        }
                    })
                    chunk_counter += 1
                else:
                    # Break into overlapping windows
                    page_chunks = self._sliding_window_chunks(page_text)
                    for idx, chunk_str in enumerate(page_chunks):
                        chunks.append({
                            "chunk_id": f"{document_id}_p{page_num}_c{idx}",
                            "document_id": document_id,
                            "filename": filename,
                            "page_number": page_num,
                            "chunk_index": idx,
                            "content": chunk_str,
                            "metadata": {
                                "page_number": page_num,
                                "filename": filename
                            }
                        })
                        chunk_counter += 1
        else:
            # Fallback when page blocks are not separated
            raw_chunks = self._sliding_window_chunks(full_text)
            for idx, chunk_str in enumerate(raw_chunks):
                chunks.append({
                    "chunk_id": f"{document_id}_c{idx}",
                    "document_id": document_id,
                    "filename": filename,
                    "page_number": 1,
                    "chunk_index": idx,
                    "content": chunk_str,
                    "metadata": {"filename": filename}
                })

        return chunks

    def _sliding_window_chunks(self, text: str) -> List[str]:
        """Split text by paragraphs and sliding window."""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if current_len + len(para) > self.chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                # Retain last paragraph for overlap if reasonable
                if len(current_chunk[-1]) <= self.chunk_overlap:
                    current_chunk = [current_chunk[-1], para]
                    current_len = len(current_chunk[0]) + len(para)
                else:
                    current_chunk = [para]
                    current_len = len(para)
            else:
                current_chunk.append(para)
                current_len += len(para)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [text[:self.chunk_size]]

    def retrieve_context(
        self,
        query: str,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
        top_k: int = 6
    ) -> Dict[str, Any]:
        """
        Retrieve relevant chunks and construct grounded context for a query.
        Detects specific page references in the query (e.g., 'page 5').
        """
        # Detect page number reference in the user's question
        page_ref_match = re.search(r"\bpage\s+(\d+)\b", query, re.IGNORECASE)
        page_number = int(page_ref_match.group(1)) if page_ref_match else None

        chunks = document_store.search_chunks(
            query=query,
            session_id=session_id,
            document_id=document_id,
            page_number=page_number,
            top_k=top_k
        )

        formatted_sections = []
        source_pages = set()
        source_docs = set()

        for chunk in chunks:
            p_num = chunk.get("page_number", 1)
            fname = chunk.get("filename", "Document")
            source_pages.add(p_num)
            source_docs.add(fname)
            formatted_sections.append(
                f"--- [Document: {fname} | Page: {p_num}] ---\n{chunk.get('content', '')}"
            )

        context_text = "\n\n".join(formatted_sections)

        return {
            "context_text": context_text,
            "chunks": chunks,
            "source_pages": sorted(list(source_pages)),
            "source_docs": sorted(list(source_docs)),
            "targeted_page": page_number
        }

    def get_session_documents(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all active documents associated with a session."""
        return document_store.get_session_documents(session_id)


document_service = DocumentService()
