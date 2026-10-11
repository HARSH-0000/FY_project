import fitz  # PyMuPDF
from typing import Dict
from app.core import logger


class PDFParser:
    """Parser for PDF documents."""
    
    def parse(self, file_path: str) -> Dict:
        """
        Parse PDF document.
        
        Returns:
            Dict with text_content and metadata
        """
        try:
            logger.info(f"Parsing PDF: {file_path}")
            
            doc = fitz.open(file_path)
            
            # Extract text from all pages
            text_content = []
            metadata = {
                "total_pages": len(doc),
                "pages": []
            }
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                text_content.append(f"\n--- Page {page_num + 1} ---\n{text}")
                
                metadata["pages"].append({
                    "page_number": page_num + 1,
                    "char_count": len(text)
                })
            
            # Get document metadata
            pdf_metadata = doc.metadata
            if pdf_metadata:
                metadata["title"] = pdf_metadata.get("title", "")
                metadata["author"] = pdf_metadata.get("author", "")
                metadata["subject"] = pdf_metadata.get("subject", "")
                metadata["creator"] = pdf_metadata.get("creator", "")
            
            doc.close()
            
            full_text = "\n".join(text_content)
            
            logger.info(f"PDF parsed successfully: {len(doc)} pages, {len(full_text)} characters")
            
            return {
                "text_content": full_text,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to parse PDF {file_path}: {e}")
            raise


# Global PDF parser instance
pdf_parser = PDFParser()
