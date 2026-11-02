from app.services.llm import llm_service
from app.core import logger


SIMPLE_SYSTEM_PROMPT = """You are a senior FinTech and financial intelligence expert assistant.
Your role is to provide thorough, accurate, and comprehensive answers to financial questions with clear explanations, practical examples, formulas, and calculations.

TEMPORAL CONTEXT REQUIREMENTS:
- When discussing financial data (interest rates, prices, revenues, ratios), include current year context (2026) or specify if discussing historical/hypothetical scenarios.
- For real financial products (bank rates, insurance premiums), explicitly state if data is current (2026) or indicative/example values.
- Format: "Current home loan rates range from 8-9% (2026)" or "For example, a typical rate might be 8.5% (indicative value, 2026)"

CURRENCY REQUIREMENTS:
- Default currency: Indian Rupees (₹)
- Use Indian financial notation: Crore (Cr), Lakh (L) - e.g., "₹100 Cr", "₹5 Lakh"
- When discussing international companies, specify currency: "Revenue: $50B (FY2026)" or "Revenue: ₹4,000 Cr (FY2026)"
- For calculations and examples, use ₹ unless the user query explicitly specifies a different currency (e.g. $, €, £) or is about foreign markets

FORMATTING & OUTPUT RULES:
- Format your response directly in clean, professional Markdown for immediate reading.
- Every section and subsection title MUST start with `### ` (e.g., `### 1.1 Overview`, `### 1.2 Impact on Oil Import Bill`, `### 1.3 Ripple Effects`, `### Key Takeaways`). NEVER output raw numbers as headings without `###`.
- For mathematical formulas and calculations:
  * Present mathematical formulas using clean standard display syntax:
    $$\\text{New Import Bill} = \\text{Volume} \\times \\text{Price}_{\\text{new}}$$
    or clean readable arithmetic lines:
    `New Import Bill = 1.825 bn bbl × $92 = $168 bn ≈ ₹13.9 Trillion`
  * Never output bare unstyled brackets like `[` and `]` on isolated lines.
  * Always define variables, show substituted numbers, and clearly state the final result.
- For tables:
  * Use formatted Markdown tables (`| Takeaway / Metric | Macro & Financial Implication | Period |`).
  * TABLE COMPLETENESS MANDATE: Every table row MUST have meaningful, complete content in EVERY column. NEVER leave any column or cell blank or empty. If you list multiple takeaways, EVERY row MUST have a corresponding analytical implication.
- Use bullet points and bold text for key terms, metrics, and figures.
- Do NOT wrap your output in raw JSON or code fences like ```json. Write directly in clean, polished Markdown."""


class SimpleAgent:
    """Simple agent for handling general financial queries."""
    
    async def answer(self, query: str, conversation_facts: dict = None) -> dict:
        """Generate answer for simple query, using conversation facts if available."""
        try:
            logger.info(f"Simple agent processing query: {query}")
            
            # Check if answer can be calculated from conversation facts
            if conversation_facts:
                from app.services.fact_memory import fact_memory_service
                calculated_answer = fact_memory_service.calculate_if_possible(
                    query, conversation_facts
                )
                
                if calculated_answer:
                    logger.info("Simple agent: Using calculated answer from conversation facts")
                    return {
                        "answer": calculated_answer,
                        "route": "SIMPLE",
                        "evidence": [],
                        "sources": [{"title": "User-provided data", "url": "#", "name": "Conversation context"}]
                    }
            
            from app.core.model_config import TaskType
            from app.services.visualization import should_generate_chart

            user_msg = query
            if should_generate_chart(query):
                user_msg += "\n\nIMPORTANT: The user explicitly requested a chart/graph visualization. You MUST include a structured Markdown table (| Category/Period | Value |) with exact numerical data points so it can be accurately plotted."
            
            # Add conversation facts context if available
            if conversation_facts:
                import json
                facts_context = json.dumps(conversation_facts, indent=2)
                user_msg += f"\n\nAvailable context from conversation:\n{facts_context}"

            response = await llm_service.invoke(
                system_prompt=SIMPLE_SYSTEM_PROMPT,
                user_message=user_msg,
                task_type=TaskType.QA_STANDARD,
                stream_to_user=True
            )
            
            response_text = response.strip()
            if not response_text:
                raise ValueError("Empty LLM response")
            
            # If the model happened to return JSON, parse sections; otherwise use markdown string directly
            final_answer = response_text
            if response_text.startswith('{') and '"sections"' in response_text:
                import json
                try:
                    parsed = json.loads(response_text)
                    if parsed.get("sections"):
                        final_answer = parsed
                except Exception:
                    final_answer = response_text

            result = {
                "answer": final_answer,
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
