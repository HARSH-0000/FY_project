from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict
from datetime import datetime
import json


class WriterAgent:
    """Writer agent for creating final answers with temporal anchoring."""
    
    def _get_system_prompt(self) -> str:
        now = datetime.now()
        year = now.year if now.year >= 2026 else 2026
        date_str = now.strftime("%B %Y")
        
        return f"""You are a comprehensive research writer that creates detailed, evidence-based answers.

CURRENT TEMPORAL CONTEXT:
- Today's date is {date_str} (Current Year: {year}).
- When synthesizing and presenting comparisons or figures, prioritize the latest data ({year} / current fiscal cycle).
- REQUIREMENT: ALL financial figures, rates, metrics, and data points MUST be explicitly labeled with their exact reporting period, year, or fiscal period (e.g. FY{year}, Q3 2026, 2026 budget, September 2026).
- NEVER present financial data without its temporal context. If the year/period is unknown, state "Year Not Verified" or omit the data point.
- For comparison tables, ALWAYS include a "Year / Period" column showing the reporting period for each metric.
- When data spans multiple years, show the trend with each year labeled (e.g. "2024: $100M, 2025: $120M, 2026: $145M").

CRITICAL: You MUST respond in this JSON format:
{{
  "sections": [
    {{
      "type": "text",
      "title": "Section Title",
      "content": "Detailed, comprehensive explanation with multiple paragraphs providing thorough analysis"
    }},
    {{
      "type": "table",
      "title": "Table Title",
      "columns": ["Metric", "Country/Entity 1", "Country/Entity 2", "Year / Period"],
      "rows": [
        ["Total Defence Budget", "$86 Billion (₹7.0 Lakh Cr)", "$831.5 Billion", "{year}"],
        ["% of GDP", "1.9%", "3.1%", "{year}"]
      ]
    }}
  ]
}}

COMPREHENSIVE WRITING GUIDELINES:
RESPONSE LENGTH AND DETAIL:

- Match the response length to the complexity of the user's question.
- Simple factual questions: provide a concise answer.
- Explanatory questions: provide a clear explanation with relevant examples.
- Comparison questions: use a table when it improves clarity.
- Complex research requests: generate a detailed, multi-section report.
- Respect any response-length preference explicitly provided by the user.
- Do not repeat information across sections.
- Include only evidence relevant to the query.
- Never invent facts, financial figures, dates, or citations to make the response appear comprehensive.

Rules:
- Never generate Markdown (no #, **, *, |, tables, or code fences)
- Use text sections for comprehensive explanations and analysis
- Use table sections for detailed comparisons, financial data, metrics
- Every table row must have exactly the same number of values as columns
- Preserve all important numbers, dates, entities, evidence, and citations
- Write in a professional, authoritative tone suitable for financial analysis
- Structure the answer with logical flow from overview to detailed analysis"""

    async def write(self, query: str, evidence: List[Dict], findings_summary: str = "") -> Dict:
        """Write final answer based on evidence."""
        try:
            logger.info(f"Writer agent creating answer for: {query}")
            
            if not evidence:
                logger.warning(f"Writer agent received empty evidence for query: {query}")
                logger.info(f"Findings summary was: {findings_summary}")
                return {
                    "answer": "Insufficient information found to answer this query. Please try rephrasing your question or check if the search terms are specific enough.",
                    "key_points": [],
                    "data_summary": {},
                    "debug_info": {
                        "evidence_count": 0,
                        "findings_summary_available": bool(findings_summary)
                    }
                }
            
            # Format evidence for LLM
            evidence_context = self._format_evidence(evidence)
            
            user_message = f"""Query: {query}

Evidence and Findings:
{evidence_context}

{f"Research Summary: {findings_summary}" if findings_summary else ""}

Create a comprehensive answer based on this evidence."""
            
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=self._get_system_prompt(),
                user_message=user_message,
                task_type=TaskType.SYNTHESIS_COMPLEX
            )
            
            # Parse response
            result = self._parse_response(response)
            
            logger.info("Writer agent completed")
            return result
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Writer agent failed: {e}")
            
            # Handle budget exceeded gracefully - return evidence summary
            if "budget exceeded" in error_str.lower() or "aborted" in error_str.lower():
                logger.warning(f"Writer agent hit budget limit - generating fallback response from evidence")
                return self._generate_fallback_from_evidence(query, evidence)
            
            # For other errors, re-raise
            raise
    
    def _format_evidence(self, evidence: List[Dict]) -> str:
        """Format evidence for LLM with focused, high-quality details."""
        formatted = []
        
        # Limit to top 7 most relevant evidence items for focused analysis
        sorted_evidence = sorted(
            evidence,
            key=lambda x: x.get('confidence', 0.0),
            reverse=True
        )[:7]
        
        for idx, item in enumerate(sorted_evidence, 1):
            details = item.get('evidence_text', 'N/A')
            # Keep detail limit at 800 characters for rich context
            if len(details) > 800:
                details = details[:800] + "..."
            
            formatted.append(f"""
Evidence {idx}:
Claim: {item.get('claim', 'N/A')}
Source: {item.get('source_title', 'N/A')} ({item.get('source_url', 'N/A')})
Organization: {item.get('source_name', 'N/A')}
Details: {details}
Confidence: {item.get('confidence', 0.0):.2f}
---""")
        
        return "\n".join(formatted)
    
    def _generate_fallback_from_evidence(self, query: str, evidence: List[Dict]) -> Dict:
        """
        Generate a fallback response directly from evidence without LLM.
        Used when budget is exceeded.
        """
        from datetime import datetime
        
        # Sort by confidence and take top 7
        sorted_evidence = sorted(
            evidence,
            key=lambda x: x.get('confidence', 0.0),
            reverse=True
        )[:7]
        
        # Build a text section from evidence claims
        content_parts = []
        content_parts.append(f"Based on research findings for: {query}\n\n")
        
        for idx, item in enumerate(sorted_evidence, 1):
            claim = item.get('claim', item.get('information', 'N/A'))
            source_title = item.get('source_title', 'Unknown Source')
            
            # Truncate very long claims
            if len(claim) > 500:
                claim = claim[:500] + "..."
            
            content_parts.append(f"{idx}. {claim} (Source: {source_title})\n\n")
        
        content = "".join(content_parts)
        content += "\nNote: This response was generated directly from research findings due to system resource constraints. For a comprehensive synthesized answer, please try your query again."
        
        return {
            "answer": {
                "sections": [{
                    "type": "text",
                    "title": "Research Findings Summary",
                    "content": content
                }]
            },
            "key_points": [],
            "data_summary": {}
        }
    
    def _parse_response(self, response: str) -> Dict:
        """Parse writer response."""
        try:
            response_text = response.strip()
            
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            parsed = json.loads(response_text)
            
            # Return structured format
            return {
                "answer": parsed,  # Return the structured JSON directly
                "key_points": [],
                "data_summary": {}
            }
            
        except json.JSONDecodeError:
            # If JSON parsing fails, wrap as plain text section
            return {
                "answer": {
                    "sections": [{
                        "type": "text",
                        "title": "Answer",
                        "content": response
                    }]
                },
                "key_points": [],
                "data_summary": {}
            }


# Global writer agent instance
writer_agent = WriterAgent()
