"""
Persistent Document Store for Irium Document Intelligence.
Stores uploaded documents, chunked text, and page metadata in data/documents.db.
Provides fast FTS5 BM25 retrieval, session isolation, and chunk indexing.
"""

import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "documents.db"


class DocumentStore:
    """Manages document metadata, full texts, chunks, and FTS5 retrieval."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DB_PATH)
        self._init_db()

    def _init_db(self):
        """Create documents and chunks tables with FTS5 search index."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Documents metadata table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        document_id TEXT PRIMARY KEY,
                        session_id TEXT,
                        user_id TEXT,
                        filename TEXT NOT NULL,
                        file_type TEXT NOT NULL,
                        page_count INTEGER NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        full_text TEXT,
                        metadata TEXT,
                        created_at TEXT NOT NULL
                    )
                """)

                # Chunks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        session_id TEXT,
                        filename TEXT NOT NULL,
                        page_number INTEGER NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        metadata TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_session ON documents(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_doc ON document_chunks(document_id, page_number)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_session ON document_chunks(session_id)")

                # FTS5 Full-Text Search Virtual Table
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
                        chunk_id UNINDEXED,
                        document_id UNINDEXED,
                        session_id UNINDEXED,
                        page_number UNINDEXED,
                        content
                    )
                """)
                conn.commit()
            logger.info(f"DocumentStore initialized at: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize DocumentStore: {e}")
            raise

    def save_document(
        self,
        document_id: str,
        filename: str,
        file_type: str,
        page_count: int,
        size_bytes: int,
        full_text: str,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Save a processed document record."""
        try:
            now = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO documents (
                        document_id, session_id, user_id, filename,
                        file_type, page_count, size_bytes, full_text,
                        metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document_id,
                    session_id,
                    user_id,
                    filename,
                    file_type,
                    page_count,
                    size_bytes,
                    full_text,
                    json.dumps(metadata),
                    now
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save document {document_id}: {e}")
            return False

    def save_chunks(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        filename: Optional[str] = None
    ) -> bool:
        """Save document chunks and index them into FTS5."""
        try:
            now = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for chunk in chunks:
                    chunk_id = chunk["chunk_id"]
                    page_number = chunk.get("page_number", 1)
                    chunk_index = chunk.get("chunk_index", 0)
                    content = chunk.get("content", "")
                    meta = json.dumps(chunk.get("metadata", {}))

                    # Insert chunk
                    cursor.execute("""
                        INSERT OR REPLACE INTO document_chunks (
                            chunk_id, document_id, session_id, filename,
                            page_number, chunk_index, content, metadata, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        chunk_id,
                        document_id,
                        session_id,
                        filename or "",
                        page_number,
                        chunk_index,
                        content,
                        meta,
                        now
                    ))

                    # Insert into FTS5
                    cursor.execute("""
                        INSERT INTO document_chunks_fts (
                            chunk_id, document_id, session_id, page_number, content
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        chunk_id,
                        document_id,
                        session_id,
                        page_number,
                        content
                    ))

                conn.commit()
            logger.info(f"Saved and indexed {len(chunks)} chunks for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save chunks for document {document_id}: {e}")
            return False

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            return None

    def get_session_documents(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all documents uploaded in a chat session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT document_id, session_id, filename, file_type,
                           page_count, size_bytes, created_at, metadata
                    FROM documents
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                """, (session_id,))
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get documents for session {session_id}: {e}")
            return []

    def get_all_chunks_for_document(self, document_id: str) -> List[Dict[str, Any]]:
        """Retrieve all chunks for a document in sequential order."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT chunk_id, document_id, filename, page_number, chunk_index, content
                    FROM document_chunks
                    WHERE document_id = ?
                    ORDER BY page_number ASC, chunk_index ASC
                """, (document_id,))
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get chunks for document {document_id}: {e}")
            return []

    def search_chunks(
        self,
        query: str,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
        page_number: Optional[int] = None,
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Search document chunks using FTS5 BM25 match with page filtering and keyword relevance.
        """
        results = []
        try:
            # Clean query for FTS5 syntax
            clean_query = self._sanitize_fts_query(query)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # If specific page requested, fetch chunks from that page directly
                if page_number is not None:
                    params = []
                    sql = """
                        SELECT c.chunk_id, c.document_id, c.filename, c.page_number, c.content, 0 as rank
                        FROM document_chunks c
                        WHERE c.page_number = ?
                    """
                    params.append(page_number)
                    if document_id:
                        sql += " AND c.document_id = ?"
                        params.append(document_id)
                    elif session_id:
                        sql += " AND c.session_id = ?"
                        params.append(session_id)
                    sql += " ORDER BY c.chunk_index ASC LIMIT ?"
                    params.append(top_k)

                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    if rows:
                        return [dict(r) for r in rows]

                # FTS5 search
                if clean_query:
                    params = [clean_query]
                    sql = """
                        SELECT c.chunk_id, c.document_id, c.filename, c.page_number, c.content, f.rank
                        FROM document_chunks_fts f
                        JOIN document_chunks c ON f.chunk_id = c.chunk_id
                        WHERE document_chunks_fts MATCH ?
                    """
                    if document_id:
                        sql += " AND c.document_id = ?"
                        params.append(document_id)
                    elif session_id:
                        sql += " AND c.session_id = ?"
                        params.append(session_id)

                    sql += " ORDER BY f.rank LIMIT ?"
                    params.append(top_k)

                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    results = [dict(r) for r in rows]

                # If FTS returns few or no results (e.g. natural language queries), fallback to term-based search
                if len(results) < 2:
                    fallback_results = self._fallback_term_search(
                        query, session_id=session_id, document_id=document_id, top_k=top_k
                    )
                    # Merge avoiding duplicates
                    seen_ids = {r["chunk_id"] for r in results}
                    for fb in fallback_results:
                        if fb["chunk_id"] not in seen_ids:
                            results.append(fb)
                            seen_ids.add(fb["chunk_id"])

        except Exception as e:
            logger.error(f"FTS search failed ({e}), using fallback scan: {e}")
            results = self._fallback_term_search(query, session_id=session_id, document_id=document_id, top_k=top_k)

        return results[:top_k]

    def _sanitize_fts_query(self, query: str) -> str:
        """Extract alphanumeric words and join with OR for broad fuzzy match."""
        tokens = re.findall(r"\b[A-Za-z0-9_\-\$₹%]{2,}\b", query)
        if not tokens:
            return ""
        # Filter out common stop words
        stopwords = {"what", "when", "where", "which", "who", "whom", "this", "that", "these", "those",
                     "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "does", "did",
                     "the", "and", "or", "for", "from", "with", "about", "into", "through", "during", "after"}
        meaningful = [t for t in tokens if t.lower() not in stopwords]
        if not meaningful:
            meaningful = tokens
        return " OR ".join(f'"{t}"' for t in meaningful[:8])

    def _fallback_term_search(
        self,
        query: str,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        """Fallback keyword scanner for chunks."""
        try:
            tokens = [t.lower() for t in re.findall(r"\b\w{3,}\b", query)]
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                sql = "SELECT chunk_id, document_id, filename, page_number, content FROM document_chunks WHERE 1=1"
                params = []
                if document_id:
                    sql += " AND document_id = ?"
                    params.append(document_id)
                elif session_id:
                    sql += " AND session_id = ?"
                    params.append(session_id)
                sql += " LIMIT 50"
                cursor.execute(sql, params)
                all_chunks = [dict(r) for r in cursor.fetchall()]

            # Score each chunk by term hits
            scored = []
            for chunk in all_chunks:
                text_lower = chunk["content"].lower()
                score = sum(1 for t in tokens if t in text_lower)
                if score > 0:
                    scored.append((score, chunk))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [item[1] for item in scored[:top_k]]
        except Exception as e:
            logger.error(f"Fallback search error: {e}")
            return []

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
                cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
                cursor.execute("DELETE FROM document_chunks_fts WHERE document_id = ?", (document_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    def detach_session_documents(self, session_id: str) -> bool:
        """Detach all documents from a given session without deleting records."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE documents SET session_id = NULL WHERE session_id = ?", (session_id,))
                cursor.execute("UPDATE document_chunks SET session_id = NULL WHERE session_id = ?", (session_id,))
                cursor.execute("UPDATE document_chunks_fts SET session_id = NULL WHERE session_id = ?", (session_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to detach session {session_id}: {e}")
            return False


document_store = DocumentStore()
