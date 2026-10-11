from app.services.llm import llm_service
from app.core import logger


SIMPLE_SYSTEM_PROMPT = """You are a FinTech expert assistant specializing in financial concepts and terminology.

Your role is to provide clear, accurate, and concise answers to general financial questions.

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
- Preserve important numbers, dates, entities

Guidelines:
- Provide straightforward, educational answers
- Explain concepts clearly without unnecessary jargon
- Use examples when helpful
- Keep answers focused and relevant
- Do not make up information or cite sources
- If you're not certain about something, say so

Focus areas:
- Financial concepts (EBITDA, NPA, ROE, ROA, etc.)
- Banking terminology
- Investment concepts
- Accounting principles
- General economic concepts
- Financial ratios and metrics"""


class SimpleAgent:
    """Simple agent for handling general financial queries."""
    
    async def answer(self, query: str) -> dict:
        """Generate answer for simple query."""
        try:
            logger.info(f"Simple agent processing query: {query}")
            
            response = await llm_service.invoke(
                system_prompt=SIMPLE_SYSTEM_PROMPT,
                user_message=query,
                temperature=0.3
            )
            
            # Parse JSON response
            import json
            try:
                # Try to extract JSON from response
                response_text = response.strip()
                if response_text.startswith('```json'):
                    response_text = response_text.split('```json')[1].split('```')[0].strip()
                elif response_text.startswith('```'):
                    response_text = response_text.split('```')[1].split('```')[0].strip()
                
                structured_response = json.loads(response_text)
            except:
                # Fallback: wrap plain text response
                structured_response = {
                    "sections": [
                        {
                            "type": "text",
                            "title": "Answer",
                            "content": response
                        }
                    ]
                }
            
            result = {
                "answer": structured_response,
                "route": "SIMPLE",
                "evidence": [],
                "sources": []
            }
            
            logger.info("Simple agent completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Simple agent failed: {e}")
            raise


# Global simple agent instance
simple_agent = SimpleAgent()
