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
        
        return f"""You are a senior FinTech research analyst synthesizing evidence-based financial intelligence. Current year: {year}.

FORMATTING & QUALITY RULES:
1. Format your answer directly in clean, professional Markdown for immediate reading.
2. ALL financial figures MUST include reporting period and use Indian Rupees (₹) by default: "Revenue: ₹500 Cr (FY{year})" or "Revenue: $50B (FY{year})" if USD.
3. Every section and subsection title MUST start with `### ` (e.g., `### 1.1 Overview`, `### 1.2 Impact on Oil Import Bill`, `### 1.3 Ripple Effects`, `### Key Strategic Takeaways`). NEVER output raw numbers as headings without `###`.
4. Mathematical Formulas & Calculations:
   - Present mathematical formulas using clean standard display syntax:
     $$\\text{{New Import Bill}} = \\text{{Volume}} \\times \\text{{Price}}_{{\\text{{new}}}}$$
     or clean readable arithmetic lines:
     `New Import Bill = 1.825 bn bbl × $92 = $168 bn ≈ ₹13.9 Trillion`
   - Never output bare unstyled brackets like `[` and `]` on isolated lines without math formatting.
   - Always define variables, show substituted numbers, and clearly state the final result.
5. Structured Tables:
   - Use formatted Markdown tables (`| Takeaway / Metric | Macro & Financial Implication | Period / Scope |`).
   - TABLE COMPLETENESS MANDATE: Every table row MUST have meaningful, complete content in EVERY column. NEVER leave any column or cell blank or empty. If you list 5 takeaways, each of the 5 rows MUST have a corresponding analytical implication.
6. Use bullet points and bold text for key metrics, takeaways, and numbers.
7. Reference evidence claims without bracketed citation numbers (like [1], [2]) - sources are displayed separately.
8. State limitations when data is unavailable. Do NOT invent figures or dates.
9. Do NOT output raw JSON or code fences. Write directly in polished Markdown."""

    async def write(self, query: str, evidence: List[Dict], findings_summary: str = "") -> Dict:
        """Write final answer based on evidence."""
        try:
            logger.info(f"Writer agent creating answer for: {query}")
            
            # If no evidence, generate response from LLM's finance domain knowledge
            if not evidence:
                logger.warning(f"Writer agent received empty evidence for query: {query}")
                logger.info(f"Generating response from LLM finance knowledge (no external evidence)")
                return await self._generate_from_knowledge(query)
            
            # Format evidence for LLM
            evidence_context = self._format_evidence(evidence)
            
            from app.services.visualization import should_generate_chart
            chart_hint = "\nIMPORTANT: The user explicitly requested a chart/graph visualization. You MUST include a structured 'table' section with the exact numerical data points (periods/entities and numbers) so it can be plotted." if should_generate_chart(query) else ""

            user_message = f"""Query: {query}

Evidence and Findings:
{evidence_context}

{f"Research Summary: {findings_summary}" if findings_summary else ""}{chart_hint}

Create a comprehensive answer based on this evidence."""
            
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=self._get_system_prompt(),
                user_message=user_message,
                task_type=TaskType.SYNTHESIS_COMPLEX,
                stream_to_user=True
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
        """Format evidence concisely for LLM."""
        formatted = []
        
        # Top 7 most relevant evidence items
        sorted_evidence = sorted(
            evidence,
            key=lambda x: x.get('confidence', 0.0),
            reverse=True
        )[:7]
        
        for idx, item in enumerate(sorted_evidence, 1):
            details = item.get('evidence_text', 'N/A')
            # Reduced to 400 characters for efficient token usage
            if len(details) > 400:
                details = details[:400] + "..."
            
            formatted.append(f"[{idx}] {item.get('claim', 'N/A')}\nSource: {item.get('source_title', 'N/A')}\nURL: {item.get('source_url', 'N/A')}\nDetails: {details}\n")
        
        return "\n".join(formatted)
    
    async def _generate_from_knowledge(self, query: str) -> Dict:
        """
        Generate finance-related response from LLM's built-in knowledge when no evidence is available.
        This ensures users get helpful answers even when external search yields no results.
        """
        logger.info("Generating response from LLM finance domain knowledge")
        
        knowledge_prompt = f"""User query: "{query}"

No external evidence found. Provide a helpful response based on financial knowledge.

Guidelines:
1. Focus on fundamental concepts and principles
2. If query asks for current data, acknowledge you cannot provide real-time information
3. Suggest what type of information to look for
4. Stay within finance/business domain"""

        from app.core.model_config import TaskType
        response = await llm_service.invoke(
            system_prompt=self._get_system_prompt(),
            user_message=knowledge_prompt,
            task_type=TaskType.SYNTHESIS_COMPLEX,
            stream_to_user=True
        )
        
        # Parse response
        result = self._parse_response(response)
        
        # Add disclaimer
        if isinstance(result.get("answer"), dict) and "sections" in result["answer"]:
            result["answer"]["sections"].append({
                "type": "text",
                "title": "Note",
                "content": "Based on general financial knowledge. For current data, refer to official sources."
            })
        
        logger.info("Generated knowledge-based response")
        return result
    
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
        response_text = response.strip()
        if response_text.startswith('{') and '"sections"' in response_text:
            try:
                parsed = json.loads(response_text)
                return {
                    "answer": parsed,
                    "key_points": [],
                    "data_summary": {}
                }
            except Exception:
                pass
        
        return {
            "answer": response_text,
            "key_points": [],
            "data_summary": {}
        }


# Global writer agent instance
writer_agent = WriterAgent()
