from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict
import json


PLANNER_SYSTEM_PROMPT = """You are a research planning agent for complex FinTech queries.

Your task is to break down complex research questions into specific, actionable search tasks.

Guidelines:
- Create 2-4 focused search tasks (keep it concise)
- Each task should be specific and searchable
- Order tasks logically by importance
- Tasks should cover the most important aspects of the query
- Be specific about what information to find
- For comparisons, create separate tasks for each entity only if necessary
- Prioritize quality over quantity

Output Format:
Provide a JSON object with:
{
    "tasks": [
        {
            "task_id": 1,
            "description": "Specific task description",
            "search_query": "Optimized search query for this task",
            "expected_info": "What information we expect to find"
        }
    ],
    "strategy": "Brief explanation of the research strategy"
}

Examples:

Query: "Compare HDFC Bank and ICICI Bank's financial performance"
Tasks:
1. Find latest financial metrics for both HDFC Bank and ICICI Bank (revenue, profit, NPA)
2. Compare market capitalization and valuation multiples
3. Analyze growth trends and market position

Query: "Analyze RBI regulations on digital lending"
Tasks:
1. Find recent RBI circulars and guidelines on digital lending
2. Identify key compliance requirements and industry impact"""


class PlannerAgent:
    """Planner agent for breaking down complex queries."""
    
    async def plan(self, query: str) -> Dict:
        """Create research plan for complex query."""
        try:
            logger.info(f"Planner agent creating plan for: {query}")
            
            response = await llm_service.invoke(
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_message=f"Create a research plan for this query:\n\n{query}",
                temperature=0.2
            )
            
            # Parse response
            plan = self._parse_response(response)
            
            logger.info(f"Planner created {len(plan['tasks'])} tasks")
            return plan
            
        except Exception as e:
            logger.error(f"Planner agent failed: {e}")
            raise
    
    def _parse_response(self, response: str) -> Dict:
        """Parse planner response."""
        try:
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
            
            parsed = json.loads(response_text)
            
            return {
                "tasks": parsed.get("tasks", []),
                "strategy": parsed.get("strategy", "")
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse planner response: {e}")
            # Create a simple fallback plan
            return {
                "tasks": [
                    {
                        "task_id": 1,
                        "description": "Search for information about the query",
                        "search_query": response,
                        "expected_info": "Relevant information"
                    }
                ],
                "strategy": "Single comprehensive search"
            }


# Global planner agent instance
planner_agent = PlannerAgent()
