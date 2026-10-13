from app.services.llm import llm_service
from app.schemas.research import RouteDecision
from app.core import logger
import json
import re


ROUTER_SYSTEM_PROMPT = """You are an intelligent query router for a FinTech research system.

Your task is to classify user queries into exactly THREE tiers based on their information requirements:

**TIER 1: SIMPLE**
Choose SIMPLE when:
- The question is about general, stable financial concepts
- No current/real-time information is needed
- No external verification is required
- One straightforward answer is sufficient
- The answer is definitional or conceptual

Examples:
- "What is EBITDA?"
- "What is an NPA?"
- "What is the difference between revenue and profit?"
- "Explain inflation"
- "What is a stock?"

**TIER 2: VERIFICATION**
Choose VERIFICATION when:
- The user asks for current, factual information
- The answer needs external confirmation
- One or a few authoritative sources are sufficient
- Recent financial/regulatory information is required
- Specific numerical data or recent facts are needed

Examples:
- "What is the current RBI repo rate?"
- "What was Infosys PAT in FY2025?"
- "What is the latest SEBI regulation on digital lending?"
- "What was HDFC Bank's revenue in FY2025?"
- "What is today's USD/INR exchange rate?"

**TIER 3: COMPLEX**
Choose COMPLEX when the query requires:
- Multiple sources
- Comparison between entities
- Financial analysis
- Multi-step reasoning
- Regulatory analysis
- Investigation across different sources
- Synthesis of multiple pieces of information

Examples:
- "Compare HDFC Bank and ICICI Bank's financial performance over the last three years"
- "Analyze the impact of RBI regulations on Indian digital lending companies"
- "Compare Bajaj Finance and Shriram Finance based on profitability, asset quality and growth"
- "What are the major differences between India's banking regulations and US banking regulations?"

**CRITICAL RULES:**
1. DO NOT classify based on query length - a short query can be VERIFICATION or COMPLEX
2. Classify based on information requirements, not sentence structure
3. Current information = VERIFICATION (not SIMPLE)
4. Comparison/Analysis = COMPLEX (not VERIFICATION)
5. Multiple sources needed = COMPLEX

Return ONLY a JSON object with this exact structure:
{
    "route": "SIMPLE" | "VERIFICATION" | "COMPLEX",
    "reason": "Brief explanation of why this tier was chosen",
    "requires_current_information": boolean,
    "requires_external_search": boolean,
    "requires_multiple_sources": boolean,
    "requires_comparison": boolean,
    "requires_multi_step_reasoning": boolean
}"""


class RouterAgent:
    """Router agent that classifies queries into research tiers."""
    
    async def route(self, query: str) -> RouteDecision:
        """Route the query to the appropriate tier."""
        try:
            logger.info(f"Routing query: {query}")
            
            # Fast-path deterministic heuristics (0ms overhead)
            q_clean = query.strip().lower()

            # Check if query is explicitly a comparison / multi-entity inquiry
            is_complex_pattern = bool(re.search(r'\b(compare|versus|vs\.?|across\s+\w+\s+and\s+\w+|difference between|differences between|impact of\s+.+\s+on)\b', q_clean))

            if not is_complex_pattern:
                # 1. Definitional / conceptual queries -> Tier 1 (SIMPLE)
                is_simple_def = bool(re.search(
                    r'^(what is|define|explain|meaning of)\s+(an?\s+)?(ebitda|npa|pe ratio|sip|mutual fund|stock|bond|equity|debt|ipo|derivative|future|option|dividend|market cap)\b',
                    q_clean
                )) and not bool(re.search(r'\b(current|today|today\'?s|latest|recent|202\d|fy2\d)\b', q_clean))

                if is_simple_def:
                    logger.info(f"Fast-path heuristic routed query '{query[:40]}' to SIMPLE (0ms)")
                    return RouteDecision(
                        route="SIMPLE",
                        reason="Fast-path deterministic match for financial definition/concept",
                        requires_current_information=False,
                        requires_external_search=False,
                        requires_multiple_sources=False,
                        requires_comparison=False,
                        requires_multi_step_reasoning=False
                    )

                # 2. Current factual rate / regulation / market queries -> Tier 2 (VERIFICATION)
                is_verification_term = bool(re.search(
                    r'\b(repo rate|reverse repo|bank rate|cash reserve ratio|\bcrr\b|\bslr\b|\bmsf rate\b|inflation rate|\bcpi\b|\bwpi\b|gdp growth|exchange rate|usd/?inr|inr/?usd|forex reserve|policy rate)\b',
                    q_clean
                ))
                has_current_keyword = bool(re.search(
                    r'\b(current|today|today\'?s|latest|recent|present)\b',
                    q_clean
                ))
                is_factual_question = bool(re.search(
                    r'^(what|how much|tell me|give me|check)\b.*\b(rate|price|pat|revenue|ebitda|margin|market cap|regulation|circular|policy)\b',
                    q_clean
                ))

                if is_verification_term or (has_current_keyword and is_factual_question) or "rbi repo" in q_clean or "current rbi" in q_clean:
                    logger.info(f"Fast-path heuristic routed query '{query[:40]}' to VERIFICATION (0ms)")
                    return RouteDecision(
                        route="VERIFICATION",
                        reason="Fast-path deterministic match for current factual / search query",
                        requires_current_information=True,
                        requires_external_search=True,
                        requires_multiple_sources=False,
                        requires_comparison=False,
                        requires_multi_step_reasoning=False
                    )

            # Expanded deterministic rules: prioritize evidence-rich routes
            # Send more queries to VERIFICATION/COMPLEX for better evidence collection
            needs_real_data = bool(re.search(r'\b(interest rate|loan|bank|emi|rate|price|cost|much|amount|calculate|calculation)\b', q_clean))
            
            if is_complex_pattern or "analysis of" in q_clean or "compare" in q_clean or "trends" in q_clean:
                logger.info(f"Fast-path heuristic routed query '{query[:40]}' to COMPLEX (0ms)")
                return RouteDecision(
                    route="COMPLEX",
                    reason="Fast-path deterministic match for financial comparison / complex analysis",
                    requires_current_information=True,
                    requires_external_search=True,
                    requires_multiple_sources=True,
                    requires_comparison=True,
                    requires_multi_step_reasoning=True
                )
            elif needs_real_data and not is_simple_def:
                # Route queries about rates, loans, etc. to VERIFICATION for evidence
                logger.info(f"Fast-path heuristic routed query '{query[:40]}' to VERIFICATION (0ms) - needs real data")
                return RouteDecision(
                    route="VERIFICATION",
                    reason="Query requires real-world data and evidence",
                    requires_current_information=True,
                    requires_external_search=True,
                    requires_multiple_sources=False,
                    requires_comparison=False,
                    requires_multi_step_reasoning=False
                )

            # Fallback to LLM classifier if not deterministically matched
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=ROUTER_SYSTEM_PROMPT,
                user_message=f"Classify this query:\n\n{query}",
                task_type=TaskType.ROUTING
            )
            
            # Parse JSON response
            # Try to extract JSON from the response
            response_text = response.strip()
            
            # Handle markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # Parse JSON
            parsed = json.loads(response_text)
            decision = RouteDecision(**parsed)
            
            logger.info(f"Route decision: {decision.route} - {decision.reason}")
            return decision
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse router response as JSON: {e}")
            logger.error(f"Response was: {response}")
            # Fallback to SIMPLE if parsing fails
            return RouteDecision(
                route="SIMPLE",
                reason="Failed to parse router response, defaulting to SIMPLE",
                requires_current_information=False,
                requires_external_search=False,
                requires_multiple_sources=False,
                requires_comparison=False,
                requires_multi_step_reasoning=False
            )
        except Exception as e:
            logger.error(f"Router agent failed: {e}")
            raise


# Global router instance
router_agent = RouterAgent()
