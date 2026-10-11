from app.services.llm import llm_service
from app.core import logger
from typing import List, Dict
import json


DOCUMENT_ANALYSIS_SYSTEM_PROMPT = """You are a document analysis expert specializing in financial documents and reports.

Your task is to analyze one or multiple documents to answer user questions or perform analysis.

Capabilities:
- Summarization: Create concise summaries of documents
- Comparison: Compare multiple documents on specific criteria
- Data extraction: Extract specific financial metrics, dates, figures
- Contradiction detection: Find conflicting information between documents
- Cross-document analysis: Synthesize information across documents
- Question answering: Answer questions based on document content

Guidelines:
- Only use information explicitly in the documents
- Always cite document names and sections when possible
- Be precise with numbers, dates, and financial data
- For multi-document analysis, clearly attribute information to specific documents
- Identify contradictions or inconsistencies
- If information is not in the documents, say so clearly
- Never fabricate data or citations

Output Format:
Provide a JSON object with:
{
    "executive_summary": "Brief overview of findings",
    "key_findings": [
        {
            "finding": "Specific finding",
            "document": "Document name",
            "confidence": 0.0-1.0,
            "supporting_text": "Relevant excerpt"
        }
    ],
    "document_summaries": {
        "document_name": "Summary for this document"
    },
    "cross_document_analysis": "Analysis comparing/contrasting documents",
    "data_extracted": {
        "Any structured data found (metrics, dates, figures)"
    },
    "contradictions": [
        {
            "issue": "What contradicts",
            "document_1": "First document's position",
            "document_2": "Second document's position"
        }
    ],
    "answer": "Direct answer to the user's question",
    "limitations": "Any limitations or missing information"
}"""


class DocumentAnalysisAgent:
    """Agent for analyzing single or multiple documents."""
    
    async def analyze(self, query: str, documents: List[Dict]) -> Dict:
        """
        Analyze documents to answer a query.
        
        Args:
            query: User's analysis question
            documents: List of document dicts with 'filename', 'text_content', 'metadata'
        
        Returns:
            Analysis result
        """
        try:
            logger.info(f"Document analysis agent processing {len(documents)} documents")
            
            # Format documents for LLM
            documents_context = self._format_documents(documents)
            
            user_message = f"""Question/Task: {query}

Documents to analyze:
{documents_context}

Analyze these documents to answer the question or perform the requested analysis."""
            
            response = await llm_service.invoke(
                system_prompt=DOCUMENT_ANALYSIS_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=0.1
            )
            
            # Parse response
            result = self._parse_response(response)
            
            logger.info("Document analysis completed")
            return result
            
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            raise
    
    def _format_documents(self, documents: List[Dict]) -> str:
        """Format documents for LLM consumption."""
        formatted = []
        
        for idx, doc in enumerate(documents, 1):
            filename = doc.get("filename", f"Document {idx}")
            content = doc.get("text_content", "")
            
            # Truncate very long documents
            max_chars = 15000  # Per document limit
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n[Document truncated - showing first {max_chars} characters]"
            
            formatted.append(f"""
{'=' * 80}
DOCUMENT {idx}: {filename}
{'=' * 80}

{content}

{'=' * 80}
END OF DOCUMENT {idx}
{'=' * 80}
""")
        
        return "\n".join(formatted)
    
    def _parse_response(self, response: str) -> Dict:
        """Parse analysis response."""
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
                "executive_summary": parsed.get("executive_summary", ""),
                "key_findings": parsed.get("key_findings", []),
                "document_summaries": parsed.get("document_summaries", {}),
                "cross_document_analysis": parsed.get("cross_document_analysis", ""),
                "data_extracted": parsed.get("data_extracted", {}),
                "contradictions": parsed.get("contradictions", []),
                "answer": parsed.get("answer", ""),
                "limitations": parsed.get("limitations", "")
            }
            
        except json.JSONDecodeError:
            # If JSON parsing fails, return response as answer
            return {
                "executive_summary": "",
                "key_findings": [],
                "document_summaries": {},
                "cross_document_analysis": "",
                "data_extracted": {},
                "contradictions": [],
                "answer": response,
                "limitations": "Response format was not structured"
            }


# Global document analysis agent instance
document_analysis_agent = DocumentAnalysisAgent()
