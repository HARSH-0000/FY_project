from app.services.llm import llm_service
from app.core import logger


SIMPLE_SYSTEM_PROMPT = """You are a comprehensive FinTech expert assistant specializing in detailed financial analysis and education.

Your role is to provide thorough, accurate, and comprehensive answers to financial questions with extensive explanations and practical examples.

TEMPORAL CONTEXT REQUIREMENTS:
- When discussing financial data (interest rates, prices, revenues, ratios), include current year context (2026) or specify if discussing historical/hypothetical scenarios.
- For real financial products (bank rates, insurance premiums), explicitly state if data is current (2026) or indicative/example values.
- Format: "Current home loan rates range from 8-9% (2026)" or "For example, a typical rate might be 8.5% (indicative value, 2026)"

CRITICAL: You MUST respond with COMPLETE, VALID JSON in this EXACT format:
{
  "sections": [
    {
      "type": "text",
      "title": "Section Title",
      "content": "Comprehensive, detailed explanation with multiple paragraphs"
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

IMPORTANT JSON RULES:
- Response MUST be complete, valid JSON
- Do NOT truncate or leave JSON incomplete
- Do NOT wrap JSON in markdown code fences (no ```json or ```)
- NEVER include incomplete sections or cut-off content
- If running out of space, write fewer but complete sections
- Ensure all JSON brackets and braces are properly closed

COMPREHENSIVE RESPONSE GUIDELINES:
- Create 2-4 complete sections (not more if it risks truncation)
- Each text section should have 2-3 complete paragraphs
- Include practical examples and calculations where relevant
- Use tables for comparisons and data
- Target 1000-2500 words total
- PRIORITIZE COMPLETENESS over adding extra sections

Rules:
- Never generate Markdown (no #, **, *, |, tables, or code fences)
- Use text sections for comprehensive explanations and analysis
- Use table sections for detailed comparisons, calculations, examples
- Every table row must have exactly the same number of values as columns
- Write in professional, authoritative tone suitable for financial education
- Include specific calculations, formulas, and worked examples
- Explain technical terms and provide context

Guidelines:
- Provide comprehensive educational content with deep insights
- Explain concepts thoroughly with background context
- Use detailed examples and real-world scenarios
- Include calculations and demonstrate methods
- Provide comparative analysis and industry benchmarks
- Address common questions and considerations
- Include practical implications and decision factors
- Structure information logically from basic to advanced concepts

Focus areas:
- Detailed financial concepts and their applications
- Comprehensive banking and lending analysis  
- Investment strategies and considerations
- Accounting principles with examples
- Economic concepts and their implications
- Financial ratios, calculations, and interpretations
- Market dynamics and industry analysis"""


class SimpleAgent:
    """Simple agent for handling general financial queries."""
    
    async def answer(self, query: str) -> dict:
        """Generate answer for simple query."""
        try:
            logger.info(f"Simple agent processing query: {query}")
            
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=SIMPLE_SYSTEM_PROMPT,
                user_message=query,
                task_type=TaskType.QA_STANDARD
            )
            
            # Parse JSON response
            import json
            try:
                # Try to extract JSON from response
                response_text = response.strip()
                
                if not response_text:
                    logger.error("Simple agent received empty response from LLM")
                    raise ValueError("Empty LLM response")
                
                logger.info(f"Simple agent raw LLM response (first 200 chars): {response_text[:200]}")
                
                # Handle markdown code blocks
                if response_text.startswith('```json'):
                    response_text = response_text.split('```json')[1].split('```')[0].strip()
                    logger.info("Removed ```json markdown fence")
                elif response_text.startswith('```'):
                    response_text = response_text.split('```')[1].split('```')[0].strip()
                    logger.info("Removed ``` markdown fence")
                
                # Try to parse as JSON
                structured_response = json.loads(response_text)
                logger.info(f"Simple agent successfully parsed JSON with {len(structured_response.get('sections', []))} sections")
                
                # Validate structured response has content
                if not structured_response.get("sections"):
                    logger.warning("Simple agent: LLM returned JSON but no sections found")
                    raise ValueError("No sections in response")
                    
                # Check if sections have content
                has_content = any(
                    section.get("content", "").strip() 
                    for section in structured_response.get("sections", [])
                )
                if not has_content:
                    logger.warning("Simple agent: Sections exist but all content is empty")
                    raise ValueError("All sections have empty content")
                
            except json.JSONDecodeError as json_error:
                logger.warning(f"Simple agent JSON parsing failed: {json_error}")
                logger.info(f"Attempting alternative JSON extraction methods")
                
                # The response might be valid JSON but failed to parse
                # This could happen if the LLM output is incomplete or malformed
                # Instead of wrapping it as content, return a proper error structure
                logger.error(f"Failed to parse LLM response as JSON. Response length: {len(response)}")
                logger.error(f"Response preview: {response[:500]}")
                
                # Return a proper error structure instead of wrapping raw JSON
                structured_response = {
                    "sections": [
                        {
                            "type": "text",
                            "title": "Response Error",
                            "content": "I apologize, but I encountered an error generating a properly formatted response. Please try rephrasing your question or try again."
                        }
                    ]
                }
                
            except Exception as parse_error:
                logger.error(f"Simple agent parsing failed with exception: {parse_error}")
                structured_response = {
                    "sections": [
                        {
                            "type": "text",
                            "title": "Error",
                            "content": "I apologize, but I could not generate a response. Please try rephrasing your question."
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
