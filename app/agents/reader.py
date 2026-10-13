from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict, Optional
from datetime import datetime
import json
import re


class ReaderAgent:
    """Reader agent for analyzing search results with temporal anchoring."""
    
    def _get_system_prompt(self) -> str:
        now = datetime.now()
        year = now.year if now.year >= 2026 else 2026
        
        return f"""You are a comprehensive research reader agent that extracts detailed information from search results.

CURRENT TEMPORAL CONTEXT:
- The current year is {year}.
- REQUIREMENT: EVERY financial figure, rate, metric, or data point you extract MUST include its reporting period, year, quarter, or date.
- Format examples: "8.5% interest rate (October 2026)", "₹50,000 crore revenue (FY2026)", "$1.2B net profit (Q3 2026)"
- If you cannot determine the exact reporting period from the source, mark it as "[Period Not Verified]" but still include the finding.
- Prioritize extracting the latest figures and data points ({year} or latest available reporting period).
- DO NOT extract financial data without temporal context unless absolutely necessary.

Your task is to:
1. Read and analyze search results thoroughly
2. Extract 5 to 8 key verifiable data points relevant to the task
3. Identify important facts, figures, financial metrics, and contextual information
4. Note comprehensive source information for each piece of data
5. Provide detailed context and background for each finding

Guidelines:
- Focus on extracting comprehensive, verifiable information
- Extract specific numbers, dates, metrics, and contextual details
- Include background information and explanations
- Prefer authoritative sources and official reports
- Extract both quantitative data and qualitative insights
- Provide detailed summaries with rich context

Output Format:
Provide a JSON object with extensive findings:
{{
    "findings": [
        {{
            "information": "Detailed fact or data point with comprehensive context, year/date, and implications",
            "source_title": "Complete title of source document",
            "source_url": "Full URL of source",
            "source_name": "Official name of source organization",
            "confidence": 0.9,
            "context": "Comprehensive context explaining the significance, methodology, and broader implications of this finding"
        }}
    ],
    "summary": "Comprehensive 2-3 sentence summary covering key findings and their significance",
    "data_quality": "reliable"
}}"""

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
            
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=self._get_system_prompt(),
                user_message=user_message,
                task_type=TaskType.SUMMARIZATION
            )
            
            # Parse response with search_results fallback
            result = self._parse_response(response, search_results=search_results, task=task)
            
            logger.info(f"Reader found {len(result.get('findings', []))} findings")
            return result
            
        except Exception as e:
            logger.error(f"Reader agent failed: {e}")
            # If LLM invocation itself failed, fallback directly to search results
            fallback_findings = self._extract_from_search_results(search_results, task)
            return {
                "findings": fallback_findings,
                "summary": f"Extracted from search results ({len(fallback_findings)} sources)",
                "data_quality": "search_fallback"
            }
    
    def _format_search_results(self, results: List[Dict]) -> str:
        """Format search results for comprehensive LLM analysis."""
        formatted = []
        
        # Increase to top 5 search results for more comprehensive coverage
        for idx, result in enumerate(results[:5], 1):
            raw_content = result.get('content', 'N/A')
            # Increase content limit to 1000 characters for richer context
            if len(raw_content) > 1000:
                raw_content = raw_content[:1000] + "..."

            formatted.append(f"""
Result {idx}:
Title: {result.get('title', 'N/A')}
URL: {result.get('url', 'N/A')}
Content: {raw_content}
---""")
        
        return "\n".join(formatted)

    def _extract_from_search_results(self, search_results: Optional[List[Dict]], task: Optional[Dict] = None) -> List[Dict]:
        """Convert raw search results directly into comprehensive structured findings."""
        findings = []
        if not search_results:
            return findings

        # Increase to top 5 results for better coverage
        for idx, r in enumerate(search_results[:5], 1):
            content = (r.get("content") or "").strip()
            title = r.get("title") or (task.get("description") if task else f"Source {idx}")
            url = r.get("url") or ""
            if content:
                findings.append({
                    "information": content[:500],  # Increase content limit
                    "source_title": title,
                    "source_url": url,
                    "source_name": title[:60],  # Longer source names
                    "confidence": 0.85,
                    "context": f"Comprehensive finding relevant to {task.get('description', 'query') if task else 'search'} with detailed context from {title}"
                })
        return findings
    
    def _parse_response(
        self,
        response: str,
        search_results: Optional[List[Dict]] = None,
        task: Optional[Dict] = None
    ) -> Dict:
        """Parse reader response with multi-stage recovery and fallback."""
        response_text = response.strip()

        # Step 1: Clean markdown fences
        clean_text = response_text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json", 1)[1]
            if "```" in clean_text:
                clean_text = clean_text.split("```", 1)[0]
        elif "```" in clean_text:
            clean_text = clean_text.split("```", 1)[1]
            if "```" in clean_text:
                clean_text = clean_text.split("```", 1)[0]
        clean_text = clean_text.strip()

        # Step 2: Try standard JSON parsing
        try:
            parsed = json.loads(clean_text)
            findings = parsed.get("findings", [])
            if findings:
                return {
                    "findings": findings,
                    "summary": parsed.get("summary", ""),
                    "data_quality": parsed.get("data_quality", "reliable")
                }
        except Exception:
            pass

        # Step 3: Extract individual finding items using regex if JSON is truncated
        logger.info("Reader: Attempting robust regex recovery of findings from partial/truncated JSON.")
        recovered_findings = []

        # Find all finding objects: { "information": ..., ... }
        object_matches = re.findall(
            r'\{\s*"information"\s*:\s*"([^"]+)"[\s\S]*?"source_title"\s*:\s*"([^"]*)"[\s\S]*?"source_url"\s*:\s*"([^"]*)"',
            response_text
        )
        for info, stitle, surl in object_matches:
            if info.strip():
                recovered_findings.append({
                    "information": info.strip(),
                    "source_title": stitle.strip() or "Search Result",
                    "source_url": surl.strip(),
                    "source_name": stitle.strip() or "Search Result",
                    "confidence": 0.9,
                    "context": "Extracted via robust recovery"
                })

        # If regex matched findings, return them!
        if recovered_findings:
            logger.info(f"Reader: Successfully recovered {len(recovered_findings)} findings from truncated response.")
            return {
                "findings": recovered_findings,
                "summary": "Recovered findings from response",
                "data_quality": "recovered"
            }

        # Step 4: If LLM produced zero parseable findings, fallback to search results
        logger.warning("Reader: Zero parseable findings from LLM. Falling back to search results snippets.")
        fallback_findings = self._extract_from_search_results(search_results, task)
        return {
            "findings": fallback_findings,
            "summary": "Extracted directly from search results",
            "data_quality": "search_fallback"
        }


# Global reader agent instance
reader_agent = ReaderAgent()
