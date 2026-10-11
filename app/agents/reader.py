from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict
import json


READER_SYSTEM_PROMPT = """You are a research reader agent that extracts relevant information from search results.

Your task is to:
1. Read and analyze search results
2. Extract key information relevant to the task
3. Identify important facts, figures, and data
4. Note source information for each piece of data

Guidelines:
- Focus on factual, verifiable information
- Extract specific numbers, dates, metrics
- Note the source for each piece of information
- Prefer authoritative sources
- Be precise and accurate
- If information is unclear or missing, note it

Output Format:
Provide a JSON object with:
{
    "findings": [
        {
            "information": "Specific fact or data point",
            "source_title": "Title of source",
            "source_url": "URL of source",
            "source_name": "Name of source organization",
            "confidence": 0.0-1.0,
            "context": "Additional context if needed"
        }
    ],
    "summary": "Brief summary of findings",
    "data_quality": "Assessment of information quality"
}"""


class ReaderAgent:
    """Reader agent for analyzing search results."""
    
    async def read(self, task: Dict, search_results: List[Dict]) -> Dict:
        """Read and extract information from search results."""
        try:
            logger.info(f"Reader agent processing task: {task.get('description', 'N/A')}")
            
            if not search_results:
                return {
                    "findings": [],
                    "summary": "No search results available",
                    "data_quality": "insufficient"
                }
            
            # Format search results
            search_context = self._format_search_results(search_results)
            
            # Get LLM to extract information
            user_message = f"""Task: {task.get('description', '')}
Expected Information: {task.get('expected_info', '')}

Search Results:
{search_context}

Extract relevant information for this task."""
            
            response = await llm_service.invoke(
                system_prompt=READER_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=0.0
            )
            
            # Parse response
            result = self._parse_response(response)
            
            logger.info(f"Reader found {len(result.get('findings', []))} findings")
            return result
            
        except Exception as e:
            logger.error(f"Reader agent failed: {e}")
            raise
    
    def _format_search_results(self, results: List[Dict]) -> str:
        """Format search results for LLM."""
        formatted = []
        
        for idx, result in enumerate(results, 1):
            formatted.append(f"""
Result {idx}:
Title: {result.get('title', 'N/A')}
URL: {result.get('url', 'N/A')}
Content: {result.get('content', 'N/A')}
---""")
        
        return "\n".join(formatted)
    
    def _parse_response(self, response: str) -> Dict:
        """Parse reader response."""
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
            
            return {
                "findings": parsed.get("findings", []),
                "summary": parsed.get("summary", ""),
                "data_quality": parsed.get("data_quality", "unknown")
            }
            
        except json.JSONDecodeError:
            return {
                "findings": [],
                "summary": response,
                "data_quality": "unknown"
            }


# Global reader agent instance
reader_agent = ReaderAgent()
