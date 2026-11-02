from app.services.llm import llm_service
from app.schemas.research import RouteDecision
from app.core import logger
import json
import re
from typing import List, Dict


ROUTER_SYSTEM_PROMPT = """You are an intelligent query router for a FinTech research system.

Your task is to classify user queries into exactly THREE tiers based on their information requirements:

**TIER 1: SIMPLE**
Choose SIMPLE when:
- The question is about general, stable financial concepts
- Mathematical calculations, formula-based problems, or numerical computations (e.g., simple or compound interest, loan EMI, future/present value, NPV, IRR, CAGR, arithmetic or algebra word problems)
- Calculations where problem values/parameters are provided in the question
- No current/real-time information is needed
- No external verification or web search is required
- One straightforward answer is sufficient
- The answer is definitional, conceptual, or calculative

Examples:
- "What is EBITDA?"
- "What is an NPA?"
- "What is the difference between revenue and profit?"
- "Calculate the simple interest for 5 years on $600 at 10% for first 3 years and 20% for last 2 years"
- "Calculate the EMI for a 50 lakh loan at 8.5% for 20 years"
- "What is 18% GST on 50000?"
- "Formula to calculate CAGR with example"
- "Explain inflation"
- "What is a stock?"

**TIER 2: VERIFICATION**
Choose VERIFICATION when:
- The user asks for current, factual real-world information
- The answer needs external confirmation from live web sources
- One or a few authoritative sources are sufficient
- Recent financial/regulatory information is required
- Specific live numerical market data or recent facts are needed (e.g., current repo rate, today's stock price, latest quarterly revenue)
- DO NOT choose VERIFICATION for pure mathematical, formula-based, or numerical calculations that don't need real-world live data

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
3. Mathematical/formula/numerical calculations = SIMPLE (not VERIFICATION)
4. Current information = VERIFICATION (not SIMPLE)
5. Comparison/Analysis = COMPLEX (not VERIFICATION)
6. Multiple sources needed = COMPLEX

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
    
    def _is_math_or_calculation_query(self, q_clean: str) -> bool:
        """Detect mathematical, formula-based, numerical, and calculation queries."""
        # Live market facts exclusion: if explicitly asking for current/live real-world rates/prices without problem parameters
        has_live_keyword = bool(re.search(r'\b(current|today|today\'?s|latest|recent|live|present)\b', q_clean))
        is_live_factual_target = bool(re.search(r'\b(repo rate|reverse repo|bank rate|cpi|wpi|inflation rate|gdp|exchange rate|stock price|share price|market cap|pat|revenue|circular|regulation|policy)\b', q_clean))
        if has_live_keyword and is_live_factual_target:
            return False

        # Direct arithmetic expressions e.g. 500 * 20, 18% of 50000
        if re.search(r'\b\d+(\.\d+)?\s*[\+\-\*\/]\s*\d+(\.\d+)?\b', q_clean):
            return True
        if re.search(r'\b\d+(\.\d+)?%\s+of\s+[\$₹€£]?\d+', q_clean):
            return True

        # Explicit formula / calculation request queries
        if re.search(r'\b(formula\s+(for|to\s+calculate|of)|how\s+to\s+calculate)\b', q_clean):
            return True

        # Math / calculation action verbs
        has_calc_action = bool(re.search(r'\b(calculate|calculation|compute|computation|solve|evaluate|find\s+the|determine\s+the)\b', q_clean))

        # Financial calculation concepts & metrics
        has_calc_terms = bool(re.search(
            r'\b(simple\s+interest|compound\s+interest|principal|emi|npv|irr|cagr|roi|annuity|future\s+value|present\s+value|\bfv\b|\bpv\b|amortization|depreciation|salvage\s+value|wacc|break-?even|profit\s+margin|gross\s+margin|net\s+margin|operating\s+margin|percentage|gst|vat|tax\s+payable|yield)\b',
            q_clean
        ))

        # Numerical problem context (numbers with financial/time units, e.g. 5 years, $600, 10%, rates for first)
        has_numerical_context = bool(re.search(
            r'(\bprincipal\s+(amount|of)?\b|\b\d+\s*(years?|months?|yrs?)\b|[\$₹€£]\s*\d+|\b\d+(\.\d+)?%|\bwith\s+different\s+rates\b|\brate\s+of\s+\d+|\binterest\s+earned\b|\bat\s+\d+(\.\d+)?%)',
            q_clean
        ))

        if has_calc_action and (has_calc_terms or has_numerical_context):
            return True

        # Financial math word problems without explicit 'calculate' verb (e.g. 'The simple interest for five years on a principal amount of $600...')
        if has_calc_terms and has_numerical_context:
            return True

        # Algebraic equations / solving for variables
        if re.search(r'\b(solve\s+for\s+\w+|equation|algebra)\b', q_clean) or re.search(r'\b\d*[a-zA-Z]\s*[\+\-\*\/]\s*\d+\s*=\s*\d+\b', q_clean):
            return True

        return False

    async def route(
        self, 
        query: str,
        conversation_history: List[Dict] = None,
        conversation_facts: Dict = None
    ) -> RouteDecision:
        """Route the query to the appropriate tier with conversation context."""
        try:
            # Import fact memory service
            from app.services.fact_memory import fact_memory_service
            
            # Resolve query with conversation context if available
            resolved_query = query
            if conversation_history:
                # Extract facts from history if not provided
                if not conversation_facts:
                    conversation_facts = fact_memory_service.extract_facts_from_history(
                        conversation_history, query
                    )
                
                # Resolve implicit references in query
                if conversation_facts:
                    resolved_query = fact_memory_service.resolve_query_with_facts(
                        query, conversation_facts
                    )
                    
                    # Check if we can calculate answer directly
                    calculated_answer = fact_memory_service.calculate_if_possible(
                        query, conversation_facts
                    )
                    
                    if calculated_answer:
                        # Query can be answered by calculation - route to SIMPLE
                        logger.info(f"Query can be calculated from facts - routing to SIMPLE")
                        return RouteDecision(
                            route="SIMPLE",
                            reason="Calculation possible from user-provided facts in conversation",
                            requires_current_information=False,
                            requires_external_search=False,
                            requires_multiple_sources=False,
                            requires_comparison=False,
                            requires_multi_step_reasoning=False
                        )
            
            logger.info(f"Routing query: {resolved_query if resolved_query != query else query}")
            if resolved_query != query:
                logger.info(f"  (Resolved from: {query})")
            
            # Fast-path deterministic heuristics (0ms overhead, 0 tokens)
            q_clean = resolved_query.strip().lower()

            # Check for mathematical, calculation, formula-based, or numerical queries -> Tier 1 (SIMPLE)
            is_math_calc = self._is_math_or_calculation_query(q_clean)
            if is_math_calc:
                logger.info("Fast-path: Routed to SIMPLE (0 tokens) - mathematical/calculation query")
                return RouteDecision(
                    route="SIMPLE",
                    reason="Fast-path: Mathematical calculation/numerical problem query",
                    requires_current_information=False,
                    requires_external_search=False,
                    requires_multiple_sources=False,
                    requires_comparison=False,
                    requires_multi_step_reasoning=False
                )

            # Check if query is explicitly a comparison / multi-entity inquiry
            is_complex_pattern = bool(re.search(
                r'\b(compare|versus|vs\.?|across\s+\w+\s+and\s+\w+|difference between|differences between|impact of\s+.+\s+on)\b',
                q_clean
            ))

            if is_complex_pattern:
                logger.info(f"Fast-path: Routed to COMPLEX (0 tokens) - comparison pattern detected")
                return RouteDecision(
                    route="COMPLEX",
                    reason="Fast-path: Query contains comparison or multi-entity analysis pattern",
                    requires_current_information=True,
                    requires_external_search=True,
                    requires_multiple_sources=True,
                    requires_comparison=True,
                    requires_multi_step_reasoning=True
                )

            # Check for definitional / conceptual queries -> Tier 1 (SIMPLE)
            is_simple_def = bool(re.search(
                r'^(what is|define|explain|meaning of)\s+(an?\s+)?(ebitda|npa|pe ratio|sip|mutual fund|stock|bond|equity|debt|ipo|derivative|future|option|dividend|market cap)\b',
                q_clean
            )) and not bool(re.search(r'\b(current|today|today\'?s|latest|recent|202\d|fy2\d)\b', q_clean))

            if is_simple_def:
                logger.info(f"Fast-path: Routed to SIMPLE (0 tokens) - definitional query")
                return RouteDecision(
                    route="SIMPLE",
                    reason="Fast-path: Financial definition/concept query",
                    requires_current_information=False,
                    requires_external_search=False,
                    requires_multiple_sources=False,
                    requires_comparison=False,
                    requires_multi_step_reasoning=False
                )

            # Check for current factual rate / regulation / market queries -> Tier 2 (VERIFICATION)
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
                logger.info(f"Fast-path: Routed to VERIFICATION (0 tokens) - current factual query")
                return RouteDecision(
                    route="VERIFICATION",
                    reason="Fast-path: Current factual/search query",
                    requires_current_information=True,
                    requires_external_search=True,
                    requires_multiple_sources=False,
                    requires_comparison=False,
                    requires_multi_step_reasoning=False
                )

            # Expanded: prioritize evidence-rich routes (only real-world data queries, NOT calculations)
            needs_real_data = bool(re.search(r'\b(interest rate|loan|bank|rate|price|cost)\b', q_clean)) and not is_math_calc
            
            if "analysis of" in q_clean or "trends" in q_clean:
                logger.info(f"Fast-path: Routed to COMPLEX (0 tokens) - analysis query")
                return RouteDecision(
                    route="COMPLEX",
                    reason="Fast-path: Requires analysis or trend investigation",
                    requires_current_information=True,
                    requires_external_search=True,
                    requires_multiple_sources=True,
                    requires_comparison=False,
                    requires_multi_step_reasoning=True
                )
            elif needs_real_data and not is_simple_def:
                logger.info(f"Fast-path: Routed to VERIFICATION (0 tokens) - needs real data")
                return RouteDecision(
                    route="VERIFICATION",
                    reason="Fast-path: Requires real-world data",
                    requires_current_information=True,
                    requires_external_search=True,
                    requires_multiple_sources=False,
                    requires_comparison=False,
                    requires_multi_step_reasoning=False
                )

            # Fallback to LLM classifier if not deterministically matched
            logger.info("Router: No fast-path match, using LLM classifier")
            from app.core.model_config import TaskType
            
            # Build prompt with conversation context if available
            classifier_prompt = f"Classify this query:\n\n{resolved_query}"
            if conversation_facts:
                facts_summary = json.dumps(conversation_facts, indent=2)
                classifier_prompt += f"\n\nUser-provided context from conversation:\n{facts_summary}"
            
            response = await llm_service.invoke(
                system_prompt=ROUTER_SYSTEM_PROMPT,
                user_message=classifier_prompt,
                task_type=TaskType.ROUTING
            )
            
            # Parse JSON response
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
            
            logger.info(f"Router LLM decision: {decision.route} - {decision.reason}")
            return decision
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse router response as JSON: {e}")
            logger.error(f"Response was: '{response}'")
            
            # If response is empty or very short, it's likely a model failure
            if not response or len(response.strip()) < 10:
                logger.warning("Router received empty/short response - likely model failure")
                # For empty responses, make intelligent fallback based on query content
                q_lower = query.lower()
                if self._is_math_or_calculation_query(q_lower):
                    logger.info("Empty response fallback: routing calculation to SIMPLE")
                    return RouteDecision(
                        route="SIMPLE",
                        reason="Model failure fallback: detected mathematical/calculation pattern",
                        requires_current_information=False,
                        requires_external_search=False,
                        requires_multiple_sources=False,
                        requires_comparison=False,
                        requires_multi_step_reasoning=False
                    )
                elif any(word in q_lower for word in ['compare', 'vs', 'versus', 'difference between']):
                    logger.info("Empty response fallback: routing comparison to COMPLEX")
                    return RouteDecision(
                        route="COMPLEX",
                        reason="Model failure fallback: detected comparison pattern",
                        requires_current_information=True,
                        requires_external_search=True,
                        requires_multiple_sources=True,
                        requires_comparison=True,
                        requires_multi_step_reasoning=True
                    )
                elif any(word in q_lower for word in ['current', 'latest', 'today', 'rate', 'price']):
                    logger.info("Empty response fallback: routing current data to VERIFICATION")
                    return RouteDecision(
                        route="VERIFICATION",
                        reason="Model failure fallback: detected current data request",
                        requires_current_information=True,
                        requires_external_search=True,
                        requires_multiple_sources=False,
                        requires_comparison=False,
                        requires_multi_step_reasoning=False
                    )
            
            # Default fallback to SIMPLE if parsing fails
            logger.info("Router parsing failed: defaulting to SIMPLE tier")
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
