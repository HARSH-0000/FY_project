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
            
            # Step 1: Deterministic validation first (0 tokens)
            deterministic_result = self._deterministic_validation(query, answer, evidence)
            
            # If deterministic validation passes with high confidence, skip LLM
            if deterministic_result["is_acceptable"] and deterministic_result["quality_score"] >= 0.7:
                logger.info(f"Critic: Deterministic validation passed (0 tokens) - Score: {deterministic_result['quality_score']:.2f}")
                return deterministic_result
            
            # Step 2: LLM evaluation for edge cases or low confidence
            logger.info("Critic: Using LLM for detailed evaluation")
            return await self._llm_critique(query, answer, evidence)
            
        except Exception as e:
            logger.error(f"Critic agent failed: {e}")
            # Return a permissive critique on failure
            return {
                "quality_score": 0.6,
                "is_acceptable": True,
                "strengths": [],
                "weaknesses": [],
                "missing_information": [],
                "needs_correction": False,
                "correction_needed": "",
                "feedback": "Evaluation failed, accepting answer"
            }
    
    def _deterministic_validation(self, query: str, answer: str, evidence: list) -> Dict:
        """
        Perform deterministic quality checks without LLM.
        Returns a critique dict with quality_score and is_acceptable.
        """
        strengths = []
        weaknesses = []
        missing_info = []
        score = 0.8  # Start with high score, deduct for issues
        
        # Handle answer being a dict (structured response)
        if isinstance(answer, dict):
            import json
            answer_str = json.dumps(answer, indent=2)
        else:
            answer_str = str(answer) if answer else ""
        
        # Check 1: Answer is not empty
        if not answer_str or len(answer_str.strip()) < 20:
            weaknesses.append("Answer is too short or empty")
            score -= 0.4
        else:
            strengths.append("Answer provides substantive content")
        
        # Check 2: Evidence is present
        if not evidence or len(evidence) == 0:
            weaknesses.append("No evidence provided")
            score -= 0.2
        else:
            strengths.append(f"{len(evidence)} evidence items provided")
        
        # Check 3: Sources are cited (check for URLs in answer)
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls_in_answer = re.findall(url_pattern, answer_str)
        
        if evidence and len(evidence) > 0:
            if len(urls_in_answer) == 0:
                weaknesses.append("No source URLs cited in answer")
                score -= 0.1
            else:
                strengths.append(f"{len(urls_in_answer)} sources cited")
        
        # Check 4: Answer length is appropriate
        answer_length = len(answer_str)
        if answer_length > 100:
            strengths.append("Answer provides detailed information")
        elif answer_length < 50:
            weaknesses.append("Answer may be too brief")
            score -= 0.1
        
        # Check 5: Check for key query terms in answer (basic relevance)
        query_terms = set(query.lower().split())
        # Remove common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'compare', 'what', 'how', 'why', 'when', 'where'}
        query_terms = query_terms - common_words
        
        answer_lower = answer_str.lower()
        relevant_terms = sum(1 for term in query_terms if term in answer_lower)
        
        if relevant_terms >= len(query_terms) * 0.5:
            strengths.append("Answer addresses key query terms")
        else:
            weaknesses.append("Answer may not fully address query")
            score -= 0.15
        
        # Determine if acceptable
        is_acceptable = score >= 0.6
        
        feedback = f"Deterministic validation: {len(strengths)} strengths, {len(weaknesses)} weaknesses"
        
        return {
            "quality_score": max(0.0, min(1.0, score)),
            "is_acceptable": is_acceptable,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "missing_information": missing_info,
            "needs_correction": not is_acceptable,
            "correction_needed": "; ".join(weaknesses) if weaknesses else "",
            "feedback": feedback
        }
    
    async def _llm_critique(self, query: str, answer: str, evidence: list) -> Dict:
        """Perform LLM-based critique when deterministic validation is insufficient."""
        logger.info("Critic: Performing LLM evaluation")
        
        # Handle answer being a dict (structured response)
        if isinstance(answer, dict):
            # Convert structured answer to string for evaluation
            import json
            answer_str = json.dumps(answer, indent=2)
        else:
            answer_str = str(answer)
        
        # Format evidence summary
        evidence_summary = self._format_evidence_summary(evidence)
        
        user_message = f"""Query: {query}

Answer:
{answer_str}

Evidence Used:
{evidence_summary}

Evaluate the quality and completeness of this answer."""
        
        from app.core.model_config import TaskType
        response = await llm_service.invoke(
            system_prompt=CRITIC_SYSTEM_PROMPT,
            user_message=user_message,
            task_type=TaskType.LIGHTWEIGHT
        )
        
        # Parse response
        critique = self._parse_response(response)
        
        logger.info(f"Critic LLM evaluation: Score={critique.get('quality_score', 0):.2f}, Acceptable={critique.get('is_acceptable', False)}")
        return critique
    
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
