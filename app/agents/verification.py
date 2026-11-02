from app.services.llm import llm_service
from app.services.search import search_service
from app.core import logger
from typing import List, Dict
import json


VERIFICATION_SYSTEM_PROMPT = """You are a senior FinTech research agent that verifies factual information using web search results.

Your task is to:
1. Analyze the search results provided
2. Extract verified facts, numbers, dates, and data
3. Generate a clear, accurate, and authoritative answer

TEMPORAL VALIDATION REQUIREMENTS:
- ALL financial data (interest rates, prices, revenues, profits, ratios, metrics) MUST include the reporting period, year, quarter, or date.
- Format examples: "8.75% home loan rate (September 2026)", "₹75,000 crore market cap (Q2 FY2026)", "$500M revenue (FY2025)"
- If the reporting period is not available in the source, mark it as "[Period Not Verified]" or omit the specific figure.
- For comparison tables, ALWAYS include a "Year / Period" column.

FORMATTING & OUTPUT RULES:
- Format your response directly in clean, professional Markdown for immediate reading.
- Every section and subsection title MUST start with `### ` (e.g. `### Verified Fact`, `### 1.1 Detailed Breakdown`, `### Historical Context`, `### Key Takeaways`). NEVER output raw numbers as headings without `###`.
- For mathematical formulas and calculations:
  * Present mathematical formulas using clean standard display syntax:
    $$\\text{New Import Bill} = \\text{Volume} \\times \\text{Price}_{\\text{new}}$$
    or clean readable arithmetic lines:
    `New Import Bill = 1.825 bn bbl × $92 = $168 bn ≈ ₹13.9 Trillion`
  * Never output bare unstyled brackets like `[` and `]` on isolated lines without math formatting.
- For tables:
  * Use formatted Markdown tables (`| Entity / Metric | Value | Period / Date | Macro Implication |`).
  * TABLE COMPLETENESS MANDATE: Every table row MUST have meaningful, complete content in EVERY column. NEVER leave any column or cell blank or empty.
- Use bullet points and bold text for key metrics, figures, and dates.
- Do NOT wrap your output in raw JSON or code fences. Write directly in Markdown."""


class VerificationAgent:
    """Verification agent for fact-checking and current information."""
    
    async def verify(self, query: str) -> Dict:
        """Verify query using web search, fast-pathing through Tavily's direct answer when available."""
        try:
            logger.info(f"Verification agent processing: {query}")

            from app.agents.router import router_agent
            from app.agents.simple import simple_agent

            # Safeguard: if a mathematical / calculation query reached verification agent,
            # do not perform web search or attach external sources / "Verified Fact & Finding" title;
            # delegate directly to simple agent.
            if router_agent._is_math_or_calculation_query(query.strip().lower()):
                logger.info(f"Verification agent safeguard: query '{query[:40]}' is mathematical/calculation; delegating to simple agent")
                return await simple_agent.answer(query)
            
            # Step 1: Search with Tavily instant answer
            search_data = await search_service.search_with_context(query, search_depth="basic")
            search_results = search_data.get("results", [])
            tavily_answer = (search_data.get("answer") or "").strip()

            from app.services.visualization import should_generate_chart
            requires_chart = should_generate_chart(query)

            # Fast-path: If Tavily returned a direct authoritative answer AND no visualization was requested, construct response immediately
            uninformative_prefixes = ("i am sorry", "i could not find", "i cannot find", "there is no information")
            if (
                not requires_chart
                and tavily_answer
                and len(tavily_answer) > 20
                and not any(tavily_answer.lower().startswith(p) for p in uninformative_prefixes)
            ):
                logger.info(f"Fast-path hit: Answering query '{query[:40]}' directly via Tavily instant answer (0 LLM overhead)")
                evidence = []
                for r in search_results[:3]:
                    if r.get("content"):
                        evidence.append({
                            "claim": tavily_answer[:160] + ("..." if len(tavily_answer) > 160 else ""),
                            "source_title": r.get("title", "Official Source"),
                            "source_url": r.get("url", ""),
                            "source_name": r.get("title", "Official Source"),
                            "evidence_text": r.get("content", "")[:250],
                            "confidence": 0.95
                        })

                sources = [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "name": r.get("title", "")
                    }
                    for r in search_results[:5] if r.get("url")
                ]

                return {
                    "answer": {
                        "sections": [
                            {
                                "type": "text",
                                "title": "Verified Fact & Finding",
                                "content": tavily_answer
                            }
                        ]
                    },
                    "evidence": evidence,
                    "sources": sources,
                    "route": "VERIFICATION"
                }
            
            if not search_results:
                return {
                    "answer": {
                        "sections": [{
                            "type": "text",
                            "title": "Search Result",
                            "content": "No search results found to verify this information."
                        }]
                    },
                    "evidence": [],
                    "sources": [],
                    "route": "VERIFICATION"
                }
            
            # Step 2: Format search results for LLM
            search_context = self._format_search_results(search_results)
            
            # Step 3: Get LLM to extract and verify information
            if requires_chart:
                chart_hint = (
                    "\nCRITICAL REQUIREMENT: The user explicitly requested a chart or graph visualization.\n"
                    "You MUST include a structured 'table' section in 'sections' with columns like ['Date', 'Closing Price (INR)'] "
                    "or ['Period', 'Metric'] containing all available historical numerical data points from the search results "
                    "(e.g. daily/monthly/quarterly stock prices, highs, lows, or metrics) so a chart can be rendered. Do not omit the table."
                )
            else:
                chart_hint = ""

            user_message = f"""Query: {query}
{f"Summary Context: {tavily_answer}" if tavily_answer else ""}

Search Results:
{search_context}
{chart_hint}
Analyze these search results and provide verified information with evidence."""
            
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=VERIFICATION_SYSTEM_PROMPT,
                user_message=user_message,
                task_type=TaskType.VERIFICATION,
                stream_to_user=True
            )
            
            # Step 4: Parse response
            result = self._parse_response(response)
            result["route"] = "VERIFICATION"

            # Attach authoritative sources from search results if not already present
            if not result.get("sources") and search_results:
                result["sources"] = [
                    {
                        "title": r.get("title") or r.get("url", "Web Source"),
                        "url": r.get("url", "#"),
                        "name": r.get("source", "Web")
                    }
                    for r in search_results[:5]
                    if r.get("url")
                ]
            
            logger.info("Verification agent completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Verification agent failed: {e}")
            raise
    
    def _format_search_results(self, results: List[Dict]) -> str:
        """Format search results for LLM consumption."""
        formatted = []
        
        for idx, result in enumerate(results, 1):
            formatted.append(f"""
Result {idx}:
Title: {result.get('title', 'N/A')}
URL: {result.get('url', 'N/A')}
Content: {result.get('content', 'N/A')}
Relevance Score: {result.get('score', 0.0)}
Priority Score: {result.get('priority_score', 0.0)}
---""")
        
        return "\n".join(formatted)
    
    def _parse_response(self, response: str) -> Dict:
        """Parse LLM response into structured format with resilient JSON repair and fallback recovery."""
        response_text = response.strip()
        
        # If response is structured JSON
        if response_text.startswith('{') or '"sections"' in response_text:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text_clean = response_text[json_start:json_end if json_end != -1 else None].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text_clean = response_text[json_start:json_end if json_end != -1 else None].strip()
            else:
                response_text_clean = response_text

            # Try parsing JSON
            try:
                parsed = json.loads(response_text_clean, strict=False)
                if parsed.get("sections"):
                    return {
                        "answer": {"sections": parsed.get("sections", [])},
                        "sources": parsed.get("sources", []),
                        "evidence": parsed.get("evidence", [])
                    }
            except Exception:
                pass

        # Return clean markdown text directly
        return {
            "answer": response_text,
            "evidence": [],
            "sources": []
        }


# Global verification agent instance
verification_agent = VerificationAgent()
