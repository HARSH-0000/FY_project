from app.documents.pdf_parser import pdf_parser
from app.documents.docx_parser import docx_parser
from app.core import logger
from typing import Dict
import os


class DocumentParser:
    """Main document parser that delegates to specific parsers."""
    
    def parse(self, file_path: str, file_type: str) -> Dict:
        """
        Parse document based on file type.
        
        Args:
            file_path: Path to file
            file_type: File type (pdf, docx, txt)
        
        Returns:
            Dict with text_content and metadata
        """
        try:
            logger.info(f"Parsing document: {file_path} (type: {file_type})")
            
            if file_type == "pdf":
                return pdf_parser.parse(file_path)
            elif file_type == "docx":
                return docx_parser.parse(file_path)
            elif file_type == "txt":
                return self._parse_txt(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
                
        except Exception as e:
            logger.error(f"Document parsing failed: {e}")
            raise
    
    def _parse_txt(self, file_path: str) -> Dict:
        """Parse plain text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            metadata = {
                "char_count": len(text_content),
                "line_count": text_content.count('\n') + 1
            }
            
            logger.info(f"TXT parsed successfully: {len(text_content)} characters")
            
            return {
                "text_content": text_content,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to parse TXT {file_path}: {e}")
            raise


# Global document parser instance
document_parser = DocumentParser()
