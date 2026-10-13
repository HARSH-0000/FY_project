from app.services.llm import llm_service
from app.services.search import search_service
from app.core import logger
from typing import List, Dict
import json


VERIFICATION_SYSTEM_PROMPT = """You are a FinTech research agent that verifies factual information using web search results.

Your task is to:
1. Analyze the search results provided
2. Extract verified facts and data
3. Create evidence-backed claims
4. Generate a clear, accurate answer

TEMPORAL VALIDATION REQUIREMENTS:
- ALL financial data (interest rates, prices, revenues, profits, ratios, metrics) MUST include the reporting period, year, quarter, or date.
- Format examples: "8.75% home loan rate (September 2026)", "₹75,000 crore market cap (Q2 FY2026)", "$500M revenue (FY2025)"
- If the reporting period is not available in the source, mark it as "[Period Not Verified]" or omit the specific figure.
- NEVER present financial data without temporal context.
- For comparison tables, ALWAYS include a "Year / Period" column.

CRITICAL: You MUST respond in this JSON format:
{
  "sections": [
    {
      "type": "text",
      "title": "Section Title",
      "content": "Plain text explanation with facts and numbers"
    },
    {
      "type": "table",
      "title": "Table Title",
      "columns": ["Column 1", "Column 2"],
      "rows": [
        ["Value 1", "Value 2"],
        ["Value 3", "Value 4"]
      ]
    }
  ],
  "evidence": [
    {
      "claim": "Specific fact or data point",
      "source_title": "Title of the source",
      "source_url": "URL of the source",
      "source_name": "Name/organization of source",
      "evidence_text": "Relevant excerpt from the source",
      "confidence": 0.9
    }
  ],
  "sources": [
    {
      "title": "Source title",
      "url": "Source URL",
      "name": "Source name"
    }
  ]
}

Rules for sections:
- Never generate Markdown (no #, **, *, |, tables, or code fences)
- Use text sections for normal explanations
- Use table sections for data comparisons
- Every table row must have exactly the same number of values as columns
- Preserve important numbers, dates, entities, and citations

Guidelines:
- Only use information explicitly found in the search results
- Cite sources for every factual claim
- Prefer authoritative sources (RBI, SEBI, official reports)
- Include specific numbers, dates, and figures
- Be precise and factual
- If information is not found, say so"""


class VerificationAgent:
    """Verification agent for fact-checking and current information."""
    
    async def verify(self, query: str) -> Dict:
        """Verify query using web search, fast-pathing through Tavily's direct answer when available."""
        try:
            logger.info(f"Verification agent processing: {query}")
            
            # Step 1: Search with Tavily instant answer
            search_data = await search_service.search_with_context(query, search_depth="basic")
            search_results = search_data.get("results", [])
            tavily_answer = (search_data.get("answer") or "").strip()

            # Fast-path: If Tavily returned a direct authoritative answer, construct response immediately
            uninformative_prefixes = ("i am sorry", "i could not find", "i cannot find", "there is no information")
            if (
                tavily_answer
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
            
            # Step 2: Format search results for LLM fallback
            search_context = self._format_search_results(search_results)
            
            # Step 3: Get LLM to extract and verify information
            user_message = f"""Query: {query}

Search Results:
{search_context}

Analyze these search results and provide verified information with evidence."""
            
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=VERIFICATION_SYSTEM_PROMPT,
                user_message=user_message,
                task_type=TaskType.VERIFICATION
            )
            
            # Step 4: Parse response
            result = self._parse_response(response)
            result["route"] = "VERIFICATION"
            
            logger.info("Verification agent completed successfully via LLM fallback")
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
        """Parse LLM response into structured format."""
        try:
            # Try to extract JSON from response
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
            
            # Extract sections, evidence, and sources
            sections = parsed.get("sections", [])
            evidence = parsed.get("evidence", [])
            sources = parsed.get("sources", [])
            
            # Return structured format with sections directly in answer
            return {
                "answer": {
                    "sections": sections
                },
                "sources": sources,
                "evidence": evidence
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse as JSON: {e}")
            # Return response wrapped in structured format
            return {
                "answer": {
                    "sections": [{
                        "type": "text",
                        "title": "Answer",
                        "content": response
                    }]
                },
                "evidence": [],
                "sources": []
            }


# Global verification agent instance
verification_agent = VerificationAgent()
