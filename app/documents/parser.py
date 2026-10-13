"""
Main Document Parser for Irium
Delegates to specific parsers based on file type (PDF, Images, DOCX, TXT).
"""

from typing import Dict, Any
from app.documents.pdf_parser import pdf_parser
from app.documents.image_parser import image_parser
from app.documents.docx_parser import docx_parser
from app.core import logger


class DocumentParser:
    """Main document parser that delegates to specific parsers."""

    IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

    def parse(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Parse document based on file type.

        Args:
            file_path: Path to file
            file_type: File type (pdf, png, jpg, jpeg, webp, docx, txt)

        Returns:
            Dict with text_content, metadata, and optional pages list.
        """
        file_type = file_type.lower()
        try:
            logger.info(f"Parsing document: {file_path} (type: {file_type})")

            if file_type == "pdf":
                return pdf_parser.parse(file_path)
            elif file_type in self.IMAGE_EXTENSIONS:
                return image_parser.parse(file_path, file_type)
            elif file_type == "docx":
                return docx_parser.parse(file_path)
            elif file_type == "txt":
                return self._parse_txt(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

        except Exception as e:
            logger.error(f"Document parsing failed for {file_path}: {e}")
            raise

    def _parse_txt(self, file_path: str) -> Dict[str, Any]:
        """Parse plain text file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text_content = f.read()

            metadata = {
                "total_pages": 1,
                "char_count": len(text_content),
                "line_count": text_content.count("\n") + 1,
                "pages": [{
                    "page_number": 1,
                    "char_count": len(text_content)
                }]
            }

            logger.info(f"TXT parsed successfully: {len(text_content)} characters")

            return {
                "text_content": f"--- Page 1 ---\n{text_content}",
                "metadata": metadata,
                "pages": [{
                    "page_number": 1,
                    "text": text_content
                }]
            }

        except Exception as e:
            logger.error(f"Failed to parse TXT {file_path}: {e}")
            raise


# Global document parser instance
document_parser = DocumentParser()
