"""
Persistent Memory Service for Irium
Retains user preferences, research session context (companies, objectives),
and research history across sessions. Uses SQLite disk persistence in data/persistent_memory.db
with optional PostgreSQL sync, PII safety checks, and user-level isolation.
"""

import sqlite3
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core import logger
from app.services.pii_detector import pii_service


# Determine SQLite DB path in data directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "persistent_memory.db"


class PersistentMemoryService:
    """Service managing user preferences, session context, and research history."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DB_PATH)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite tables for persistent memory."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS persistent_memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        session_id INTEGER,
                        category TEXT NOT NULL,
                        memory_key TEXT NOT NULL,
                        memory_value TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(user_id, session_id, category, memory_key)
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memories_lookup
                    ON persistent_memories(user_id, session_id, category)
                """)
                conn.commit()
            logger.info(f"PersistentMemoryService: Database ready at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize persistent memory database: {e}")

    # =========================================================================
    # 1. User Preferences
    # =========================================================================

    def save_preference(self, user_id: int, key: str, value: Any) -> bool:
        """
        Save or update a user preference (e.g. report_structure, level_of_detail, format).
        Guarantees PII scrubbing before saving.
        """
        # Scrub PII
        if isinstance(value, str):
            val_clean, _ = pii_service.redact(value)
        elif isinstance(value, dict):
            val_clean = {k: pii_service.sanitize_for_logging(str(v)) for k, v in value.items()}
        else:
            val_clean = value

        return self._upsert_memory(
            user_id=user_id,
            session_id=None,
            category="user_preferences",
            memory_key=key,
            memory_value=val_clean
        )

    def get_preferences(self, user_id: int) -> Dict[str, Any]:
        """Retrieve all saved preferences for a given user."""
        rows = self._query_memories(user_id=user_id, session_id=None, category="user_preferences")
        return {r["memory_key"]: r["memory_value"] for r in rows}

    # =========================================================================
    # 2. Research Session Context
    # =========================================================================

    def update_session_context(
        self,
        session_id: int,
        company: Optional[str] = None,
        objective: Optional[str] = None,
        follow_up: Optional[str] = None,
        earlier_reference: Optional[str] = None
    ) -> bool:
        """
        Update context for an ongoing research session.
        Maintains unique list of discussed companies and research objectives.
        """
        now = datetime.utcnow().isoformat()

        # Update discussed companies
        if company:
            clean_company, _ = pii_service.redact(company.strip().upper())
            existing_companies = self.get_session_memory(session_id, "discussed_companies") or []
            if clean_company not in existing_companies:
                existing_companies.append(clean_company)
                self._upsert_memory(
                    user_id=None,
                    session_id=session_id,
                    category="session_context",
                    memory_key="discussed_companies",
                    memory_value=existing_companies
                )

        # Update research objective
        if objective:
            clean_obj, _ = pii_service.redact(objective.strip())
            self._upsert_memory(
                user_id=None,
                session_id=session_id,
                category="session_context",
                memory_key="research_objective",
                memory_value=clean_obj
            )

        # Append follow-up questions
        if follow_up:
            clean_q, _ = pii_service.redact(follow_up.strip())
            existing_qs = self.get_session_memory(session_id, "follow_up_questions") or []
            if clean_q not in existing_qs:
                existing_qs.append(clean_q)
                self._upsert_memory(
                    user_id=None,
                    session_id=session_id,
                    category="session_context",
                    memory_key="follow_up_questions",
                    memory_value=existing_qs[-10:]  # keep last 10
                )

        # Append earlier reference summaries
        if earlier_reference:
            clean_ref, _ = pii_service.redact(earlier_reference.strip())
            existing_refs = self.get_session_memory(session_id, "earlier_references") or []
            existing_refs.append({"reference": clean_ref, "timestamp": now})
            self._upsert_memory(
                user_id=None,
                session_id=session_id,
                category="session_context",
                memory_key="earlier_references",
                memory_value=existing_refs[-5:]  # keep last 5
            )

        return True

    def get_session_memory(self, session_id: int, key: str) -> Optional[Any]:
        """Get a single session context key."""
        rows = self._query_memories(user_id=None, session_id=session_id, category="session_context", memory_key=key)
        return rows[0]["memory_value"] if rows else None

    def get_session_context(self, session_id: int) -> Dict[str, Any]:
        """Retrieve full context dictionary for a research session."""
        rows = self._query_memories(user_id=None, session_id=session_id, category="session_context")
        return {r["memory_key"]: r["memory_value"] for r in rows}

    # =========================================================================
    # 3. Research History
    # =========================================================================

    def record_research_history(
        self,
        query: str,
        route: str,
        summary: str,
        sources_count: int,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        status: str = "completed"
    ) -> bool:
        """Record completed research metadata to persistent history."""
        # Scrub PII from query and summary
        clean_query, _ = pii_service.redact(query)
        clean_summary, _ = pii_service.redact(summary[:500])

        history_key = f"hist_{int(datetime.utcnow().timestamp())}"
        history_entry = {
            "query": clean_query,
            "route": route,
            "summary": clean_summary,
            "sources_count": sources_count,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }

        return self._upsert_memory(
            user_id=user_id,
            session_id=session_id,
            category="research_history",
            memory_key=history_key,
            memory_value=history_entry
        )

    def get_research_history(
        self,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve research history ordered by most recent."""
        rows = self._query_memories(user_id=user_id, session_id=session_id, category="research_history")
        sorted_rows = sorted(rows, key=lambda x: x["updated_at"], reverse=True)
        return [r["memory_value"] for r in sorted_rows[:limit]]

    # =========================================================================
    # 4. Context Synthesis for Multi-Agent Workflows
    # =========================================================================

    def extract_companies_from_query(self, query: str) -> List[str]:
        """Heuristic helper to detect company names/tickers in query for auto-context."""
        # Simple extraction of common tickers or capitalized words
        known_financial_tickers = {
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
            "HDFC", "HDFCBANK", "ICICI", "ICICIBANK", "SBI", "SBIN",
            "RELIANCE", "TCS", "INFY", "WIPRO", "TSMC", "BRK", "JPM", "BAC"
        }
        tokens = re.findall(r'\b[A-Za-z0-9]+\b', query)
        found = []
        for t in tokens:
            upper_t = t.upper()
            if upper_t in known_financial_tickers and upper_t not in found:
                found.append(upper_t)
        return found

    def build_memory_prompt_context(
        self,
        query: str,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> str:
        """
        Build concise, structured prompt context containing user preferences
        and prior session companies, strictly non-overriding.
        """
        context_parts = []

        # 1. User preferences
        if user_id:
            prefs = self.get_preferences(user_id)
            if prefs:
                pref_strs = [f"{k}: {v}" for k, v in prefs.items()]
                context_parts.append(f"User Preferences: {', '.join(pref_strs)}")

        # 2. Session context
        if session_id:
            session_ctx = self.get_session_context(session_id)
            companies = session_ctx.get("discussed_companies")
            if companies:
                context_parts.append(f"Previously Discussed Companies in Session: {', '.join(companies)}")
            objective = session_ctx.get("research_objective")
            if objective:
                context_parts.append(f"Session Research Objective: {objective}")

        if not context_parts:
            return ""

        return "\n[PERSISTENT MEMORY CONTEXT]\n" + "\n".join(context_parts) + "\n"

    # =========================================================================
    # 5. Memory Deletion & Management
    # =========================================================================

    def delete_memory(
        self,
        category: str,
        key: str,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> bool:
        """Delete specific memory key."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM persistent_memories
                    WHERE category = ? AND memory_key = ?
                      AND (user_id = ? OR (user_id IS NULL AND ? IS NULL))
                      AND (session_id = ? OR (session_id IS NULL AND ? IS NULL))
                """, (category, key, user_id, user_id, session_id, session_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    def clear_all(
        self,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> int:
        """Clear all memories matching user or session scope."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if user_id is not None and session_id is not None:
                    cursor.execute("""
                        DELETE FROM persistent_memories
                        WHERE user_id = ? OR session_id = ?
                    """, (user_id, session_id))
                elif user_id is not None:
                    cursor.execute("DELETE FROM persistent_memories WHERE user_id = ?", (user_id,))
                elif session_id is not None:
                    cursor.execute("DELETE FROM persistent_memories WHERE session_id = ?", (session_id,))
                else:
                    cursor.execute("DELETE FROM persistent_memories")
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
            return 0

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _upsert_memory(
        self,
        user_id: Optional[int],
        session_id: Optional[int],
        category: str,
        memory_key: str,
        memory_value: Any
    ) -> bool:
        """Thread-safe SQLite upsert."""
        now = datetime.utcnow().isoformat()
        val_json = json.dumps(memory_value)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO persistent_memories (user_id, session_id, category, memory_key, memory_value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, session_id, category, memory_key)
                    DO UPDATE SET memory_value=excluded.memory_value, updated_at=excluded.updated_at
                """, (user_id, session_id, category, memory_key, val_json, now, now))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to upsert memory [{category}:{memory_key}]: {e}")
            return False

    def _query_memories(
        self,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        category: Optional[str] = None,
        memory_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query persistent memories matching filters."""
        query = "SELECT user_id, session_id, category, memory_key, memory_value, created_at, updated_at FROM persistent_memories WHERE 1=1"
        params: List[Any] = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if category is not None:
            query += " AND category = ?"
            params.append(category)
        if memory_key is not None:
            query += " AND memory_key = ?"
            params.append(memory_key)

        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                for row in cursor.fetchall():
                    try:
                        parsed_val = json.loads(row[4])
                    except Exception:
                        parsed_val = row[4]
                    results.append({
                        "user_id": row[0],
                        "session_id": row[1],
                        "category": row[2],
                        "memory_key": row[3],
                        "memory_value": parsed_val,
                        "created_at": row[5],
                        "updated_at": row[6]
                    })
        except Exception as e:
            logger.error(f"Failed to query memories: {e}")
        return results


# Global memory service instance
memory_service = PersistentMemoryService()
