"""
Document Analysis Agent for Irium FinTech System.
Specializes in financial document analysis, numerical extraction, financial ratios,
chart & table interpretation, cross-document comparison, and evidence-grounded QA.
"""

from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict, Any, Optional
import json
import re

GROUNDED_SYSTEM_PROMPT = """You are Irium Document Intelligence, an expert AI FinTech analyst.
Your task is to analyze financial documents, PDFs, reports, and visual charts to answer user questions with strict grounding in the provided document evidence.

CORE INSTRUCTIONS:
1. DOCUMENT GROUNDING & COMPREHENSIVE RESPONSES:
   - When answering questions about the uploaded document, base your analysis strictly on the provided document excerpts and evidence.
   - Do NOT invent or hallucinate figures that are claimed to be from the document.
   - If the user asks a question, concept, or comparison that the uploaded document DOES NOT contain information about (such as general institutional inquiries like Income Tax Department vs Vigilance Department, or general financial/economic definitions):
     Clearly clarify that this topic is not covered in the uploaded document, and then provide a thorough, accurate, and comprehensive response answering the user's question in full detail.
     Format the preamble as:
     `*(Note: The uploaded document does not contain information regarding this topic. Providing institutional analysis on the query:)*`

2. NUMERICAL & FINANCIAL PRECISION:
   - Distinguish clearly between values EXPLICITLY STATED in the document and any values calculated by you (e.g. "Reported in document: $450M; Calculated YoY growth: +12.5%").
   - Do NOT calculate financial ratios if the necessary input values are unavailable or ambiguous.
   - Include currencies ($ , ₹ , €), units (Millions, Billions, Crores), and fiscal years/dates exactly as reported.

3. PAGE CITATIONS & ATTRIBUTION:
   - Always cite the specific page or source for document findings and numbers using format: `[Page X]` or `[filename, Page X]`.
   - When discussing charts or images, reference the visual explicitly (e.g. `[Page 1 Visual Analysis]`).
   - For general institutional answers not derived from document pages, page citations are not required.

4. INTENTS SUPPORTED:
   - Summarization: Concise executive summary, major milestones, and strategic takeaways.
   - Numerical Extraction: Net profit, revenue, EBITDA, cash flows, margins, debt, assets.
   - Risk Identification: Operational, financial, regulatory, and market risks stated in the report.
   - Chart/Table Interpretation: Trends, axis ranges, legends, table comparisons.
   - Cross-Document Comparison: Compare metrics side-by-side when multiple reports are uploaded.
   - General & Institutional Inquiries: Comparative mandates, legal frameworks, and jurisdictional responsibilities.
   - Page-Specific Inquiries: When asked about a specific page (e.g. "Explain page 5"), focus on that page's contents.

5. OUTPUT FORMAT:
   - Format cleanly in professional Markdown with clear section headings, bullet points, and tables where suitable.
"""


class DocumentAnalysisAgent:
    """Agent for grounded analysis of uploaded documents and charts."""

    async def answer_general_query(self, query: str, history_context: str = "") -> str:
        """Answer a general or domain query when no document content is relevant."""
        prompt = f"""You are Irium, an expert AI FinTech and institutional research assistant.
The user has asked a question in a chat session where an uploaded document is active, but the document does not contain content relevant to this question.

USER QUESTION:
{query}

{history_context}
INSTRUCTIONS:
1. Provide a comprehensive, clear, structured, and authoritative answer addressing the user's query in full detail (for example, if comparing government/financial entities like Income Tax Department vs Vigilance Department, thoroughly explain their mandates, jurisdiction, statutory powers, governing acts, and key differences).
2. Start your response with a brief, clear introductory notice:
*(Note: The uploaded document does not contain information regarding this topic. Providing institutional analysis on {query}:)*
3. Use clean Markdown formatting with clear section headings, bullet points, and comparison tables where helpful.
"""
        from app.core.model_config import TaskType
        return await llm_service.invoke(
            system_prompt="You are Irium, an expert AI FinTech and institutional research assistant.",
            user_message=prompt,
            task_type=TaskType.QA_STANDARD
        )

    async def analyze(
        self,
        query: str,
        documents: Optional[List[Dict[str, Any]]] = None,
        retrieved_context: Optional[str] = None,
        source_pages: Optional[List[int]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Execute grounded analysis for a user query.
        
        Args:
            query: User's question or instruction
            documents: Optional list of documents uploaded in the current turn
            retrieved_context: Context chunks retrieved from document store
            source_pages: List of page numbers present in retrieved context
            conversation_history: Recent conversation turns for resolving follow-up references
            
        Returns:
            Dict containing answer, source pages, and metadata.
        """
        try:
            logger.info(f"DocumentAnalysisAgent analyzing query: {query}")

            # Assemble document context
            context_blocks = []

            # 1. Add retrieved chunks if provided (for larger documents or follow-ups)
            if retrieved_context:
                context_blocks.append(f"### RETRIEVED DOCUMENT EVIDENCE:\n{retrieved_context}")

            # 2. Add raw documents text if provided and not overly large
            if documents:
                for idx, doc in enumerate(documents, 1):
                    fname = doc.get("filename", f"Document {idx}")
                    content = doc.get("text_content", "")
                    # Cap single document preview to avoid context blowup
                    max_chars = 18000
                    if len(content) > max_chars:
                        content = content[:max_chars] + f"\n\n[... Excerpt truncated for length - first {max_chars} chars shown ...]"
                    context_blocks.append(f"### DOCUMENT {idx}: {fname}\n{content}")

            # 3. Format conversation history context for resolving follow-ups
            history_context = ""
            if conversation_history:
                recent_turns = conversation_history[-4:]
                history_lines = [f"{t.get('role', 'user').capitalize()}: {t.get('content', '')}" for t in recent_turns]
                history_context = "### RECENT CONVERSATION TURNS (for reference resolution):\n" + "\n".join(history_lines) + "\n\n"

            full_context = "\n\n".join(context_blocks)
            if not full_context.strip():
                logger.info(f"No document context available for query '{query}'; answering as general/domain query.")
                general_answer = await self.answer_general_query(query, history_context)
                return {
                    "answer": general_answer.strip(),
                    "evidence": [],
                    "source_pages": [],
                    "is_general_query": True
                }

            # 4. Construct user message prompt
            user_message = f"""{history_context}### USER QUESTION:
{query}

### RELEVANT DOCUMENT EXCERPTS & EVIDENCE:
{full_context}

Please provide a structured, evidence-grounded answer addressing the question directly. Include page references [Page X] where applicable."""

            # 5. Invoke LLM with complex document reasoning model (openai/gpt-oss-120b)
            from app.core.model_config import TaskType
            response = await llm_service.invoke(
                system_prompt=GROUNDED_SYSTEM_PROMPT,
                user_message=user_message,
                task_type=TaskType.DOCUMENT_REASONING
            )

            # 6. Extract cited pages from response and context
            cited_pages = self._extract_cited_pages(response, source_pages)

            logger.info(f"Document analysis completed successfully (citations: {cited_pages})")

            return {
                "answer": response.strip(),
                "evidence": [full_context[:1000]],
                "source_pages": cited_pages
            }

        except Exception as e:
            logger.error(f"Document analysis agent failed: {e}", exc_info=True)
            raise

    def _extract_cited_pages(self, answer_text: str, fallback_pages: Optional[List[int]]) -> List[int]:
        """Extract cited page numbers from the generated response or context."""
        found = set()
        matches = re.findall(r"\[Page\s+(\d+)\]", answer_text, re.IGNORECASE)
        for m in matches:
            found.add(int(m))

        if not found and fallback_pages:
            return fallback_pages[:4]

        return sorted(list(found))


document_analysis_agent = DocumentAnalysisAgent()
