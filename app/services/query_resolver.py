"""
Query Resolver Service - Context-Aware Query Resolution for IRIUM

Resolves ambiguous or referential follow-up queries using conversation history
before domain validation, query routing, and research execution.
"""

import json
import re
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from app.core import logger
from app.core.model_config import TaskType
from app.services.llm import llm_service


class QueryIntent(str, Enum):
    NEW_QUERY = "NEW_QUERY"
    FOLLOW_UP = "FOLLOW_UP"
    AMBIGUOUS_CLARIFICATION = "AMBIGUOUS_CLARIFICATION"
    UNRELATED = "UNRELATED"


class ResolvedQuery(BaseModel):
    """Structured result of context-aware query resolution."""
    original_query: str
    resolved_query: str
    intent: QueryIntent
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    confidence: float = 1.0
    reason: str = ""


RESOLVER_SYSTEM_PROMPT = """You are a conversational query resolution specialist for IRIUM, a financial and economic research assistant.

Your task is to analyze the user's latest query in the context of recent conversation history and return a structured JSON decision.

### INSTRUCTIONS:
1. Determine the user's INTENT from these 4 categories:
   - "FOLLOW_UP": The query refers to, expands upon, asks for examples of, asks for specific institutional reports/assessments on, or continues a topic from the conversation history (e.g. "Explain in detail", "Why?", "Give me an example", "What about bond yields?", "How does this affect inflation?", "UN development Programme assessment", "World Bank estimates", "Compare them").
   - "NEW_QUERY": The query is a complete, self-contained question with its own standalone subject (e.g. "What is EBITDA?", "Write a Python script to sort a list", "Analyze Apple's balance sheet"). CRITICAL: If the user asks a completely new question (even if technical or non-financial), NEVER inherit or merge the previous financial topic!
   - "AMBIGUOUS_CLARIFICATION": The query is too vague or ambiguous to resolve even with history, or there is no history and the message is an incomplete fragment (e.g. "Explain in detail" with no prior context).
   - "UNRELATED": The query is completely unrelated to finance/economics and does not refer to previous context.

2. Generate the "resolved_query":
   - For "FOLLOW_UP": Rewrite the query into a fully self-contained, standalone question incorporating the relevant entities, topics, and metrics from the conversation history.
     Example: Prior topic was "Explain the influence of Middle East conflicts on GDP growth", follow-up is "Explain in detail." -> resolved_query: "Explain in detail how Middle East conflicts affect GDP growth."
     Example: Prior topic was "Explain the influence of Middle East conflicts on GDP growth", follow-up is "UN development Programme assessment" -> resolved_query: "Analyze the UN Development Programme (UNDP) assessment of economic losses and GDP impact caused by Middle East conflicts."
     Example: Prior topic was "Analyze the impact of oil prices on inflation", follow-up is "Give me an example." -> resolved_query: "Give an example of how changes in oil prices affect inflation."
     Example: Prior topic was "Explain RBI monetary policy", follow-up is "What about bond yields?" -> resolved_query: "How does RBI monetary policy affect bond yields?"
     Example: Prior topic was "Compare India's and China's GDP growth", follow-up is "What about inflation?" -> resolved_query: "Compare India's and China's inflation rates."
   - For "NEW_QUERY" or "UNRELATED": Keep the original query EXACTLY as written. NEVER append or fabricate previous topics.
   - For "AMBIGUOUS_CLARIFICATION": Set "requires_clarification": true and provide a polite "clarification_question".

3. Return ONLY valid JSON in this format:
{
    "intent": "FOLLOW_UP" | "NEW_QUERY" | "AMBIGUOUS_CLARIFICATION" | "UNRELATED",
    "resolved_query": "The standalone query string",
    "requires_clarification": boolean,
    "clarification_question": "string or null",
    "confidence": float between 0.0 and 1.0,
    "reason": "Brief explanation of resolution"
}
"""


class QueryResolverService:
    """Service for resolving conversational context in user queries."""

    def __init__(self):
        # Patterns that strongly indicate a follow-up or referential query
        self.follow_up_patterns = [
            r'^(?:explain|elaborate|clarify|detail|expand)\s+(?:in\s+detail|in\s+details|further|more|on\s+this|on\s+that)\b',
            r'^(?:explain|elaborate)\s+(?:more|further)\b',
            r'^(?:give|provide|show)\s+(?:me\s+)?(?:an?\s+)?example\b',
            r'^(?:why|how|what)\s*\??$',
            r'^(?:why\s+so|how\s+come|what\s+about\s+it)\b',
            r'^what\s+about\s+([a-zA-Z\s]+)\??$',
            r'^(?:how\s+does\s+this|how\s+does\s+that|how\s+do\s+these)\b',
            r'^(?:and|also|what\s+if)\b',
            r'^(?:tell\s+me\s+more|continue|go\s+on)\b',
            r'^(?:more\s+details|more\s+info)\b',
        ]

    def _is_vague_fragment(self, query: str) -> bool:
        """Check if query is an incomplete fragment that requires prior context."""
        q = query.strip().lower()
        if q in ["explain in detail", "explain in details", "explain more", "elaborate", 
                 "why?", "why", "how?", "how", "give me an example", "give an example",
                 "tell me more", "more details", "what about it?", "what about it", "continue"]:
            return True
        return any(re.match(pattern, q) for pattern in self.follow_up_patterns)

    def _extract_last_user_topic(self, history: List[Dict], current_query: str = "") -> Optional[str]:
        """Extract the most recent user query topic from history, excluding the current query."""
        norm_current = current_query.strip().lower()
        for turn in reversed(history):
            if turn.get("role") == "user" and turn.get("content"):
                content = turn["content"].strip()
                if norm_current and content.lower() == norm_current:
                    continue
                if self._is_vague_fragment(content):
                    continue
                return content
        return None

    async def resolve_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> ResolvedQuery:
        """
        Resolve a user query in the context of recent conversation history.

        Args:
            query: Raw user message
            conversation_history: List of recent turns [{role: 'user'|'assistant', content: str}]

        Returns:
            ResolvedQuery object with resolved_query, intent, and clarification info
        """
        trimmed_query = query.strip()
        if not trimmed_query:
            return ResolvedQuery(
                original_query=query,
                resolved_query=query,
                intent=QueryIntent.AMBIGUOUS_CLARIFICATION,
                requires_clarification=True,
                clarification_question="Please enter a valid financial or economic query.",
                confidence=1.0,
                reason="Empty query"
            )

        # Normalize and filter conversation history
        valid_history = []
        if conversation_history:
            for turn in conversation_history:
                if isinstance(turn, dict) and turn.get("content"):
                    role = turn.get("role", "user")
                    content = str(turn.get("content", "")).strip()
                    if content:
                        valid_history.append({"role": role, "content": content})

        # Remove trailing turn if it matches the current user query to prevent self-referencing
        if valid_history and valid_history[-1].get("role") == "user":
            if valid_history[-1].get("content", "").strip().lower() == trimmed_query.lower():
                valid_history = valid_history[:-1]

        # Keep last 6 turns (up to 3 complete exchanges) to avoid token bloat
        recent_history = valid_history[-6:]

        # Case 1: Empty conversation history
        if not recent_history:
            if self._is_vague_fragment(trimmed_query):
                logger.info(f"Query resolution: Fragment '{trimmed_query}' with no history requires clarification")
                return ResolvedQuery(
                    original_query=trimmed_query,
                    resolved_query=trimmed_query,
                    intent=QueryIntent.AMBIGUOUS_CLARIFICATION,
                    requires_clarification=True,
                    clarification_question=(
                        "Could you please specify which financial, economic, or business topic "
                        "you would like me to explain?"
                    ),
                    confidence=0.95,
                    reason="Incomplete query fragment with no conversation history"
                )
            
            # Standalone query with no history
            return ResolvedQuery(
                original_query=trimmed_query,
                resolved_query=trimmed_query,
                intent=QueryIntent.NEW_QUERY,
                requires_clarification=False,
                confidence=1.0,
                reason="Standalone query with no conversation history"
            )

        # Case 2: Conversation history is present
        # Format history for LLM
        formatted_history_lines = []
        for turn in recent_history:
            role_label = "User" if turn["role"] == "user" else "Assistant"
            # Truncate assistant content to 250 chars to keep context tight and relevant
            content = turn["content"]
            if turn["role"] == "assistant" and len(content) > 250:
                content = content[:250] + "..."
            formatted_history_lines.append(f"{role_label}: {content}")
        
        history_str = "\n".join(formatted_history_lines)

        user_prompt = (
            f"### CONVERSATION HISTORY:\n"
            f"{history_str}\n\n"
            f"### CURRENT USER QUERY:\n"
            f"{trimmed_query}\n\n"
            f"Resolve the query according to the instructions and return JSON."
        )

        try:
            logger.info(f"Query resolution: Analyzing query '{trimmed_query}' with {len(recent_history)} history turns")
            response = await llm_service.invoke(
                system_prompt=RESOLVER_SYSTEM_PROMPT,
                user_message=user_prompt,
                task_type=TaskType.ROUTING
            )

            response_text = response.strip()
            # Clean markdown codeblocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            parsed = json.loads(response_text)
            intent_str = parsed.get("intent", "NEW_QUERY").upper()
            try:
                intent = QueryIntent(intent_str)
            except ValueError:
                intent = QueryIntent.NEW_QUERY

            resolved_text = parsed.get("resolved_query", trimmed_query).strip() or trimmed_query
            requires_clarification = bool(parsed.get("requires_clarification", False))
            clarification_question = parsed.get("clarification_question")

            # Fallback sanity check: If intent is NEW_QUERY or UNRELATED, ensure we NEVER fabricate or append previous topics
            if intent in [QueryIntent.NEW_QUERY, QueryIntent.UNRELATED]:
                resolved_text = trimmed_query
                requires_clarification = False

            if requires_clarification and not clarification_question:
                clarification_question = (
                    "Could you please specify which financial, economic, or business topic "
                    "you would like me to explain?"
                )

            logger.info(
                f"Query resolution result: intent={intent.value}, "
                f"original='{trimmed_query}', resolved='{resolved_text}', "
                f"requires_clarification={requires_clarification}"
            )

            return ResolvedQuery(
                original_query=trimmed_query,
                resolved_query=resolved_text,
                intent=intent,
                requires_clarification=requires_clarification,
                clarification_question=clarification_question,
                confidence=float(parsed.get("confidence", 0.9)),
                reason=parsed.get("reason", "Resolved via context model")
            )

        except Exception as e:
            logger.warning(f"LLM query resolution failed ({e}), using safe deterministic fallback")
            return self._fallback_resolve(trimmed_query, recent_history)

    def _fallback_resolve(self, query: str, history: List[Dict]) -> ResolvedQuery:
        """Deterministic fallback when LLM invocation fails or is unavailable."""
        q_lower = query.lower()
        last_topic = self._extract_last_user_topic(history, current_query=query)

        # If query is a clear follow-up fragment and we have a previous user topic
        if last_topic and (self._is_vague_fragment(query) or "detail" in q_lower or "example" in q_lower or "why" in q_lower):
            if any(term in q_lower for term in ["detail", "elaborate", "expand"]):
                if last_topic.lower().startswith("explain "):
                    resolved = f"Explain in detail {last_topic[8:]}"
                else:
                    resolved = f"Explain in detail how {last_topic}"
            elif any(term in q_lower for term in ["example", "instance"]):
                resolved = f"Give an example of how {last_topic}"
            elif "why" in q_lower:
                resolved = f"Why is that the case regarding {last_topic}?"
            else:
                resolved = f"{query} regarding {last_topic}"

            return ResolvedQuery(
                original_query=query,
                resolved_query=resolved,
                intent=QueryIntent.FOLLOW_UP,
                requires_clarification=False,
                confidence=0.85,
                reason="Resolved via rule-based fallback"
            )

        # Causal follow-up: "how does this affect X?"
        affect_match = re.search(r'how\s+does\s+(?:this|that|it)\s+affect\s+(.+?)\??$', query, re.IGNORECASE)
        if affect_match and last_topic:
            target = affect_match.group(1).strip()
            clean_topic = last_topic
            if clean_topic.lower().startswith("explain "):
                clean_topic = clean_topic[8:].strip()
            resolved = f"How does {clean_topic} affect {target}?"
            return ResolvedQuery(
                original_query=query,
                resolved_query=resolved,
                intent=QueryIntent.FOLLOW_UP,
                requires_clarification=False,
                confidence=0.85,
                reason="Resolved causal follow-up via rule-based fallback"
            )

        # What about X?
        what_about_match = re.match(r'^what\s+about\s+(.+?)\??$', query, re.IGNORECASE)
        if what_about_match and last_topic:
            target = what_about_match.group(1).strip()
            clean_topic = last_topic
            if clean_topic.lower().startswith("explain "):
                clean_topic = clean_topic[8:].strip()
            resolved = f"What about {target} in relation to {clean_topic}?"
            return ResolvedQuery(
                original_query=query,
                resolved_query=resolved,
                intent=QueryIntent.FOLLOW_UP,
                requires_clarification=False,
                confidence=0.85,
                reason="Resolved 'what about' via rule-based fallback"
            )

        # Institutional or topic assessment follow-up (e.g. "UN development Programme assessment", "UNDP report", "World Bank study")
        inst_match = re.search(r'\b(un\s+development\s+programme|undp|world\s+bank|imf|oecd|wto)\b', q_lower)
        if inst_match and last_topic:
            clean_topic = last_topic
            if clean_topic.lower().startswith("explain "):
                clean_topic = clean_topic[8:].strip()
            resolved = f"{query.strip()} regarding the economic impact of {clean_topic}"
            return ResolvedQuery(
                original_query=query,
                resolved_query=resolved,
                intent=QueryIntent.FOLLOW_UP,
                requires_clarification=False,
                confidence=0.9,
                reason="Resolved institutional assessment follow-up via rule-based fallback"
            )

        # If query is an incomplete fragment with no prior topic, require clarification
        if self._is_vague_fragment(query) and not last_topic:
            return ResolvedQuery(
                original_query=query,
                resolved_query=query,
                intent=QueryIntent.AMBIGUOUS_CLARIFICATION,
                requires_clarification=True,
                clarification_question=(
                    "Could you please specify which financial, economic, or business topic "
                    "you would like me to explain?"
                ),
                confidence=0.9,
                reason="Ambiguous fragment with no prior context in fallback"
            )

        # Otherwise treat as standalone query without fabricating context
        return ResolvedQuery(
            original_query=query,
            resolved_query=query,
            intent=QueryIntent.NEW_QUERY,
            requires_clarification=False,
            confidence=0.7,
            reason="Treated as standalone query in fallback"
        )


# Global singleton instance
query_resolver = QueryResolverService()
