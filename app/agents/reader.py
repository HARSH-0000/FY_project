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
        
        return f"""Extract key financial data from search results. Current year: {year}.

RULES:
1. Every financial figure MUST include its reporting period: "Revenue: $50B (FY{year})", "Market cap: $800B (Oct {year})"
2. Extract 3-5 key facts per task (not 8+)
3. Focus on numbers, dates, metrics relevant to the research task
4. Include source URL for each fact

Output JSON:
{{
    "findings": [
        {{
            "information": "Concise fact with year/period and metric",
            "source_url": "URL",
            "source_title": "Title",
            "confidence": 0.9,
            "context": "Brief explanation (1-2 sentences)"
        }}
    ],
    "summary": "1-sentence summary of key findings"
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
            
            num_findings = len(result.get('findings', []))
            logger.info(f"Reader extracted {num_findings} findings")
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
        """Format search results concisely for LLM analysis."""
        formatted = []
        
        # Use top 3 search results to reduce token usage
        for idx, result in enumerate(results[:3], 1):
            raw_content = result.get('content', 'N/A')
            # Reduced to 400 characters for efficient token usage
            if len(raw_content) > 400:
                raw_content = raw_content[:400] + "..."

            formatted.append(f"[{idx}] {result.get('title', 'N/A')}\n{raw_content}\nURL: {result.get('url', 'N/A')}\n")
        
        return "\n".join(formatted)

    def _extract_from_search_results(self, search_results: Optional[List[Dict]], task: Optional[Dict] = None) -> List[Dict]:
        """Convert raw search results directly into structured findings."""
        findings = []
        if not search_results:
            return findings

        # Use top 3 results for efficiency
        for idx, r in enumerate(search_results[:3], 1):
            content = (r.get("content") or "").strip()
            title = r.get("title") or (task.get("description") if task else f"Source {idx}")
            url = r.get("url") or ""
            if content:
                findings.append({
                    "information": content[:300],  # Reduced from 500 to 300
                    "source_title": title,
                    "source_url": url,
                    "source_name": title[:40],  # Reduced from 60 to 40
                    "confidence": 0.85,
                    "context": f"Finding from {title[:30]}"
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
