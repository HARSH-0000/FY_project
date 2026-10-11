from app.services.llm import llm_service
from app.core import logger
from typing import Dict
import json


CRITIC_SYSTEM_PROMPT = """You are a research quality critic that evaluates answers for accuracy and completeness.

Your task is to:
1. Evaluate if the answer adequately addresses the query
2. Check if claims are properly supported by evidence
3. Identify gaps or missing information
4. Assess overall quality and accuracy
5. Determine if corrective action is needed

Evaluation Criteria:
- Does the answer directly address the query?
- Are all claims backed by evidence?
- Is the information comprehensive?
- Are sources credible and properly cited?
- Is any critical information missing?
- Are there contradictions or inconsistencies?

Scoring Guidelines:
- 0.8-1.0: Excellent - Comprehensive, well-supported, addresses query fully
- 0.6-0.79: Good - Addresses query adequately, minor gaps acceptable
- 0.4-0.59: Fair - Partial answer, significant gaps but some value
- 0.0-0.39: Poor - Missing critical information or major inaccuracies

**Be lenient**: If the answer provides useful information and addresses the main query, 
mark it as acceptable even if some details are missing. Only request correction if the 
answer is fundamentally incomplete or incorrect.

Output Format:
Provide a JSON object with:
{
    "quality_score": 0.0-1.0,
    "is_acceptable": true/false,
    "strengths": ["List of strengths"],
    "weaknesses": ["List of weaknesses"],
    "missing_information": ["What's missing, if anything"],
    "needs_correction": true/false,
    "correction_needed": "What needs to be fixed or researched further",
    "feedback": "Overall assessment"
}"""


class CriticAgent:
    """Critic agent for evaluating answer quality."""
    
    async def critique(self, query: str, answer: str, evidence: list) -> Dict:
        """Critique the answer quality."""
        try:
            logger.info(f"Critic agent evaluating answer for: {query}")
            
            # Format evidence summary
            evidence_summary = self._format_evidence_summary(evidence)
            
            user_message = f"""Query: {query}

Answer:
{answer}

Evidence Used:
{evidence_summary}

Evaluate the quality and completeness of this answer."""
            
            response = await llm_service.invoke(
                system_prompt=CRITIC_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=0.2
            )
            
            # Parse response
            critique = self._parse_response(response)
            
            logger.info(f"Critic evaluation: Score={critique.get('quality_score', 0):.2f}, Acceptable={critique.get('is_acceptable', False)}")
            return critique
            
        except Exception as e:
            logger.error(f"Critic agent failed: {e}")
            # Return a permissive critique on failure
            return {
                "quality_score": 0.7,
                "is_acceptable": True,
                "strengths": [],
                "weaknesses": [],
                "missing_information": [],
                "needs_correction": False,
                "correction_needed": "",
                "feedback": "Evaluation failed, accepting answer"
            }
    
    def _format_evidence_summary(self, evidence: list) -> str:
        """Format evidence summary for critic."""
        if not evidence:
            return "No evidence provided"
        
        formatted = []
        for idx, item in enumerate(evidence[:5], 1):  # Show first 5
            formatted.append(f"{idx}. {item.get('claim', 'N/A')} (Source: {item.get('source_title', 'N/A')})")
        
        if len(evidence) > 5:
            formatted.append(f"... and {len(evidence) - 5} more evidence items")
        
        return "\n".join(formatted)
    
    def _parse_response(self, response: str) -> Dict:
        """Parse critic response."""
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
                "quality_score": parsed.get("quality_score", 0.5),
                "is_acceptable": parsed.get("is_acceptable", False),
                "strengths": parsed.get("strengths", []),
                "weaknesses": parsed.get("weaknesses", []),
                "missing_information": parsed.get("missing_information", []),
                "needs_correction": parsed.get("needs_correction", False),
                "correction_needed": parsed.get("correction_needed", ""),
                "feedback": parsed.get("feedback", "")
            }
            
        except json.JSONDecodeError:
            # Default to acceptable if parsing fails
            return {
                "quality_score": 0.7,
                "is_acceptable": True,
                "strengths": [],
                "weaknesses": [],
                "missing_information": [],
                "needs_correction": False,
                "correction_needed": "",
                "feedback": response
            }


# Global critic agent instance
critic_agent = CriticAgent()
