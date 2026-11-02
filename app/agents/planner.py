from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict, Optional
from datetime import datetime
import json
import re


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
            
            # Try template-based planning first (0 tokens for common patterns)
            template_plan = self._try_template_planning(query)
            if template_plan:
                logger.info(f"Planner: Using template (0 LLM tokens, {len(template_plan['tasks'])} tasks)")
                return template_plan
            
            # Fallback to LLM for complex queries
            logger.info("Planner: Using LLM for dynamic planning")
            return await self._llm_planning(query)
            
        except Exception as e:
            logger.error(f"Planner agent failed: {e}")
            raise
    
    def _try_template_planning(self, query: str) -> Optional[Dict]:
        """
        Try to generate a plan using deterministic templates for common patterns.
        Returns None if no template matches.
        """
        query_lower = query.lower().strip()
        now = datetime.now()
        year = now.year if now.year >= 2026 else 2026
        
        # Pattern 1: "Compare X and Y" - more flexible matching
        # Handles: "Compare Tesla and Toyota", "Compare the performance of X and Y"
        compare_match = re.search(
            r'compare\s+(?:the\s+)?(?:financial\s+performance|market\s+position|[\w\s]+?\s+of\s+)?(.+?)\s+and\s+(.+?)(?:\s+in\s+|,\s+focusing\s+on|$)',
            query_lower,
            re.IGNORECASE
        )
        
        if compare_match:
            entity1_raw = compare_match.group(1).strip()
            entity2_raw = compare_match.group(2).strip()
            
            # Extract entity names (last 1-3 words are typically the entity)
            entity1 = ' '.join(entity1_raw.split()[-2:])  # Last 2 words
            entity2 = ' '.join(entity2_raw.split()[-2:])  # Last 2 words
            
            # Clean up
            entity1 = entity1.replace("'s", "").replace("the", "").strip()
            entity2 = entity2.replace("'s", "").replace("the", "").strip()
            
            # If entities look valid (not empty, not too long)
            if entity1 and entity2 and len(entity1.split()) <= 3 and len(entity2.split()) <= 3:
                # Extract dimensions from query
                dimensions = None
                if "focusing on" in query_lower:
                    dimensions = query_lower.split("focusing on")[1].strip()
                elif "in terms of" in query_lower:
                    dimensions = query_lower.split("in terms of")[1].strip()
                
                # Determine metrics from query or use defaults
                metrics = self._extract_metrics(query_lower, dimensions)
                metrics_str = " ".join(metrics)
                
                tasks = [
                    {
                        "task_id": 1,
                        "description": f"Find {entity1} {year} data: {metrics_str}",
                        "search_query": f"{entity1} {year} {metrics_str} financial results performance",
                        "expected_info": f"{entity1} financial and operational metrics for {year}"
                    },
                    {
                        "task_id": 2,
                        "description": f"Find {entity2} {year} data: {metrics_str}",
                        "search_query": f"{entity2} {year} {metrics_str} financial results performance",
                        "expected_info": f"{entity2} financial and operational metrics for {year}"
                    }
                ]
                
                logger.info(f"Template matched: {entity1} vs {entity2}")
                return {
                    "tasks": tasks,
                    "strategy": f"Direct comparison: Research {entity1} and {entity2} independently, then synthesize findings."
                }
        
        # Pattern 2: "X vs Y" shorthand
        vs_match = re.search(r'(\w+(?:\s+\w+)?)\s+vs\.?\s+(\w+(?:\s+\w+)?)', query_lower, re.IGNORECASE)
        if vs_match:
            entity1 = vs_match.group(1).strip()
            entity2 = vs_match.group(2).strip()
            metrics = self._extract_metrics(query_lower, None)
            metrics_str = " ".join(metrics)
            
            tasks = [
                {
                    "task_id": 1,
                    "description": f"Research {entity1} {year} {metrics_str}",
                    "search_query": f"{entity1} {year} {metrics_str} latest data",
                    "expected_info": f"{entity1} key metrics for {year}"
                },
                {
                    "task_id": 2,
                    "description": f"Research {entity2} {year} {metrics_str}",
                    "search_query": f"{entity2} {year} {metrics_str} latest data",
                    "expected_info": f"{entity2} key metrics for {year}"
                }
            ]
            
            return {
                "tasks": tasks,
                "strategy": f"Comparison template: Research both entities and compare findings."
            }
        
        # No template match
        return None
    
    def _extract_metrics(self, query: str, dimensions: Optional[str]) -> List[str]:
        """Extract relevant metrics from query."""
        default_metrics = ["financial performance", "key metrics"]
        
        # Use dimensions if provided
        if dimensions:
            return [dimensions.strip()]
        
        # Detect common financial metrics in query
        metrics = []
        if any(term in query for term in ["revenue", "sales", "income"]):
            metrics.append("revenue")
        if any(term in query for term in ["profit", "earnings", "net income"]):
            metrics.append("profitability")
        if any(term in query for term in ["market cap", "valuation", "stock price"]):
            metrics.append("market capitalization")
        if any(term in query for term in ["strategy", "plan", "approach", "electric vehicle", "ev production"]):
            metrics.append("strategy")
        if any(term in query for term in ["growth", "expansion"]):
            metrics.append("growth")
        if any(term in query for term in ["debt", "leverage", "balance sheet"]):
            metrics.append("financial position")
        
        return metrics if metrics else default_metrics
    
    async def _llm_planning(self, query: str) -> Dict:
        """Use LLM for dynamic planning when templates don't match."""
        from app.core.model_config import TaskType
        response = await llm_service.invoke(
            system_prompt=self._get_system_prompt(),
            user_message=f"Create a research plan for this query:\n\n{query}",
            task_type=TaskType.LIGHTWEIGHT
        )
        
        # Parse response
        plan = self._parse_response(response)
        
        logger.info(f"Planner created {len(plan['tasks'])} tasks via LLM")
        return plan
    
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
