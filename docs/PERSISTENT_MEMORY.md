# Irium Persistent Memory Specification

## Overview
Irium includes a multi-category Persistent Memory architecture designed to retain user preferences, research session context, and research history across sessions.

---

## What is Stored

### 1. User Preferences
- **`report_structure`**: Preferred document layout (e.g. `executive_summary_with_risks`, `detailed_tables`, `bulleted_risks`).
- **`level_of_detail`**: Analytical depth (e.g. `concise`, `comprehensive`, `deep_dive`).
- **`financial_analysis_format`**: Financial focal perspective (e.g. `valuation_centric`, `risk_centric`, `regulatory_centric`).

### 2. Research Session Context
- **`discussed_companies`**: Set of financial entities and tickers analyzed during the session (e.g. `["HDFCBANK", "ICICIBANK"]`).
- **`research_objective`**: The user's overarching financial question or thesis.
- **`follow_up_questions`**: Relevant follow-up questions generated or asked in previous turns.
- **`earlier_references`**: Synopses and key metrics from prior research dossiers in the session.

### 3. Research History
- **`query`**: The sanitized inquiry.
- **`route`**: Routing tier (`SIMPLE`, `VERIFICATION`, `COMPLEX`).
- **`summary`**: Concise answer summary.
- **`sources_count`**: Number of authoritative sources consulted.
- **`timestamp`**: UTC timestamp of execution.

---

## Where It is Stored

1. **Storage Engine**:
   - Primary: SQLite disk database located at `data/persistent_memory.db` for zero-configuration, cross-restart local persistence.
   - Production / Cluster: PostgreSQL `persistent_memories` table mapped via SQLAlchemy models in `app/database/models.py`.
2. **PII Protection**:
   - All memories pass through `pii_service.redact()` before insertion into persistent storage. Credit cards, Aadhaar, PAN, SSN, and private phone numbers are never persisted.
3. **Tenant & User Isolation**:
   - Memories are partitioned strictly by `user_id` and `session_id`. User A cannot query or mutate User B's memories.

---

## How It is Retrieved & Used

- **Non-Overriding Prompt Context**:
  When a user submits a research query, `PersistentMemoryService.build_memory_prompt_context` synthesizes a non-overriding guidance block:
  ```
  [PERSISTENT MEMORY CONTEXT]
  User Preferences: report_structure: executive_summary, level_of_detail: deep_dive
  Previously Discussed Companies in Session: HDFCBANK, ICICIBANK
  ```
  This guides the Writer and Planner agents to adopt the user's favorite style without altering verified factual data or overriding direct user prompt instructions.

---

## How It Can Be Deleted

1. **Specific Memory Deletion**:
   - `DELETE /api/memory` with payload:
     ```json
     {
       "category": "user_preferences",
       "key": "report_structure"
     }
     ```
2. **Clear All**:
   - `POST /api/memory/clear?session_id=123` clears session-level context.
   - `POST /api/memory/clear` clears scoped user memories.
