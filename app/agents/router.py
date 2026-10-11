from app.services.llm import llm_service
from app.schemas.research import RouteDecision
from app.core import logger
import json


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
            
            # Get LLM response
            response = await llm_service.invoke(
                system_prompt=ROUTER_SYSTEM_PROMPT,
                user_message=f"Classify this query:\n\n{query}",
                temperature=0.0
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
