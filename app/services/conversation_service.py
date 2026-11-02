"""
Conversation History Service for Irium
Provides thread-safe persistent conversation turn tracking per conversation_id
using SQLite in the data directory. Ensures conversation isolation and dialogue continuity.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from app.core import logger
from app.services.pii_detector import pii_service

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CONV_DB_PATH = DATA_DIR / "conversation_history.db"


class ConversationService:
    """Manages multi-turn conversation history per conversation_id."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or CONV_DB_PATH)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite tables for conversation turns."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conv_lookup
                    ON conversation_turns(conversation_id, id)
                """)
                conn.commit()
            logger.info(f"ConversationService: Database ready at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize conversation history database: {e}")

    def get_history(self, conversation_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Retrieve recent conversation turns for a conversation_id.
        
        Args:
            conversation_id: Unique conversation thread ID
            limit: Maximum number of recent turns to retrieve
            
        Returns:
            List of turn dictionaries: [{"role": "user"|"assistant", "content": "..."}]
        """
        if not conversation_id or conversation_id == "default":
            return []

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Get the most recent N turns in ascending order
                cursor.execute("""
                    SELECT role, content FROM (
                        SELECT role, content, id FROM conversation_turns
                        WHERE conversation_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                    ) ORDER BY id ASC
                """, (conversation_id, limit))
                rows = cursor.fetchall()
                return [{"role": row[0], "content": row[1]} for row in rows]
        except Exception as e:
            logger.error(f"Failed to get conversation history for {conversation_id}: {e}")
            return []

    def add_turn(self, conversation_id: str, role: str, content: str) -> bool:
        """
        Add a turn to conversation history.
        
        Args:
            conversation_id: Unique conversation thread ID
            role: "user" or "assistant"
            content: Message text
            
        Returns:
            True if inserted, False otherwise
        """
        if not conversation_id or conversation_id == "default" or not content or not content.strip():
            return False

        trimmed_content = content.strip()
        # Truncate content to 2000 chars to avoid DB bloat while keeping full context
        if len(trimmed_content) > 2000:
            trimmed_content = trimmed_content[:2000]

        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Deduplication check: check if last turn for this conversation is identical
                cursor.execute("""
                    SELECT role, content FROM conversation_turns
                    WHERE conversation_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (conversation_id,))
                last_turn = cursor.fetchone()
                if last_turn and last_turn[0] == role and last_turn[1] == trimmed_content:
                    logger.debug(f"Skipping duplicate conversation turn for {conversation_id}")
                    return True

                cursor.execute("""
                    INSERT INTO conversation_turns (conversation_id, role, content, created_at)
                    VALUES (?, ?, ?, ?)
                """, (conversation_id, role, trimmed_content, now))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add conversation turn for {conversation_id}: {e}")
            return False

    def clear_history(self, conversation_id: str) -> int:
        """Clear all turns for a specific conversation_id."""
        if not conversation_id:
            return 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM conversation_turns WHERE conversation_id = ?", (conversation_id,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to clear conversation history for {conversation_id}: {e}")
            return 0


# Global singleton instance
conversation_service = ConversationService()
