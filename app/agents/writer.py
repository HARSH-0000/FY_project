from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict
import json


WRITER_SYSTEM_PROMPT = """You are a FinTech research writer that creates comprehensive, evidence-based answers.

Your task is to:
1. Synthesize information from research findings
2. Create a clear, well-structured answer
3. Support all claims with evidence
4. Provide citations and sources
5. Present data in an organized manner

CRITICAL: You MUST respond in this JSON format:
{
  "sections": [
    {
      "type": "text",
      "title": "Section Title",
      "content": "Plain text explanation"
    },
    {
      "type": "table",
      "title": "Table Title",
      "columns": ["Column 1", "Column 2", "Column 3"],
      "rows": [
        ["Value 1", "Value 2", "Value 3"],
        ["Value 4", "Value 5", "Value 6"]
      ]
    }
  ]
}

Rules:
- Never generate Markdown (no #, **, *, |, tables, or code fences)
- Use text sections for normal explanations
- Use table sections for comparisons, financial data, year-wise data, company/sector comparisons
- Every table row must have exactly the same number of values as columns
- Keep table cells concise and readable
- Preserve important numbers, dates, entities, evidence, and citations

Guidelines:
- Write in a professional, informative tone
- Structure the answer logically with multiple sections if needed
- Use specific numbers, dates, and facts from evidence
- Reference sources in the content
- For comparisons, create tables with clear columns
- Be comprehensive but concise
- Only use information from the provided evidence"""


class WriterAgent:
    """Writer agent for creating final answers."""
    
    async def write(self, query: str, evidence: List[Dict], findings_summary: str = "") -> Dict:
        """Write final answer based on evidence."""
        try:
            logger.info(f"Writer agent creating answer for: {query}")
            
            if not evidence:
                return {
                    "answer": "Insufficient information found to answer this query.",
                    "key_points": [],
                    "data_summary": {}
                }
            
            # Format evidence for LLM
            evidence_context = self._format_evidence(evidence)
            
            user_message = f"""Query: {query}

Evidence and Findings:
{evidence_context}

{f"Research Summary: {findings_summary}" if findings_summary else ""}

Create a comprehensive answer based on this evidence."""
            
            response = await llm_service.invoke(
                system_prompt=WRITER_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=0.3
            )
            
            # Parse response
            result = self._parse_response(response)
            
            logger.info("Writer agent completed")
            return result
            
        except Exception as e:
            logger.error(f"Writer agent failed: {e}")
            raise
    
    def _format_evidence(self, evidence: List[Dict]) -> str:
        """Format evidence for LLM."""
        formatted = []
        
        for idx, item in enumerate(evidence, 1):
            formatted.append(f"""
Evidence {idx}:
Claim: {item.get('claim', 'N/A')}
Source: {item.get('source_title', 'N/A')} ({item.get('source_url', 'N/A')})
Details: {item.get('evidence_text', 'N/A')}
Confidence: {item.get('confidence', 0.0):.2f}
---""")
        
        return "\n".join(formatted)
    
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
