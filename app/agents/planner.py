from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict
from datetime import datetime
import json


class PlannerAgent:
    """Planner agent for breaking down complex queries with temporal anchoring."""
    
    def _get_system_prompt(self) -> str:
        now = datetime.now()
        year = now.year if now.year >= 2026 else 2026
        date_str = now.strftime("%B %Y")
        
        return f"""You are a research planning agent for complex financial, economic, and strategic queries.

TEMPORAL CONTEXT:
- Today's date is {date_str} (Current Year: {year}).
- Current fiscal cycles are FY{year} / FY{year-1}-{str(year)[2:]} or FY{year}-{str(year+1)[2:]}.
- CRITICAL: When researching recent, current, or comparative figures, you MUST generate search queries targeting the current year ({year}) or latest available data.
- NEVER search for outdated historical years (such as 2023 or 2024) unless the user explicitly requested historical data for those years.

Guidelines:
- Create 2-3 focused search tasks (MAX 3 tasks for fast parallel execution). Keep it concise.
- Each task should have a clear, targeted search query explicitly referencing {year} or current period.
- For comparisons, create 2 direct tasks (one for each entity/metric or direct comparative search).
- Prioritize current data quality and execution speed.
- Make search queries SPECIFIC with exact company names, financial metrics, and time periods.

Output Format:
Provide a JSON object with:
{{
    "tasks": [
        {{
            "task_id": 1,
            "description": "Specific task description targeting {year} data",
            "search_query": "Optimized search query with {year} and specific metrics",
            "expected_info": "What information we expect to find"
        }}
    ],
    "strategy": "Brief explanation of the research strategy"
}}

Examples:

Query: "Compare defence budget of india and usa"
Tasks:
1. Search India defence budget {year} total allocation and breakdown
2. Search United States defence budget {year} (NDAA/DoD) total allocation and breakdown

Query: "Compare HDFC Bank and ICICI Bank's financial performance"
Tasks:
1. Find HDFC Bank FY{year} financial results revenue profit NPA ratios
2. Find ICICI Bank FY{year} financial results revenue profit NPA ratios"""

    async def plan(self, query: str) -> Dict:
        """Create research plan for complex query."""
        try:
            logger.info(f"Planner agent creating plan for: {query}")
            
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=self._get_system_prompt(),
                user_message=f"Create a research plan for this query:\n\n{query}",
                task_type=TaskType.LIGHTWEIGHT
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
