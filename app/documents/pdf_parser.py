"""
Advanced PDF Parser for Irium Document Intelligence.
Handles text-based PDFs, scanned PDFs (via OCR/Gemini Vision), and mixed PDFs.
Preserves page boundaries, tables, layout metadata, and extracts per-page structure.
"""

import fitz  # PyMuPDF
from typing import Dict, Any, List
from app.core import logger, settings

SCANNED_PAGE_PROMPT = """You are an OCR and document intelligence engine.
Transcribe and extract ALL text, tables, financial figures, headings, and notes from this scanned page image.
Preserve exact numbers, currencies, percentages, dates, and column headers.
Do NOT omit or summarize any details. Output the complete extracted text faithfully.
"""


class PDFParser:
    """Parser for text-based, scanned, and mixed PDF documents."""

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse PDF document, handling selectable text and applying OCR to scanned pages.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dict with 'text_content', 'metadata', and 'pages' list.
        """
        try:
            logger.info(f"Parsing PDF document: {file_path}")
            doc = fitz.open(file_path)
            total_pages = len(doc)

            text_content_blocks = []
            pages_data: List[Dict[str, Any]] = []
            scanned_pages_count = 0

            # Extract document metadata before iterating
            pdf_meta = doc.metadata or {}
            metadata = {
                "total_pages": total_pages,
                "title": pdf_meta.get("title", ""),
                "author": pdf_meta.get("author", ""),
                "subject": pdf_meta.get("subject", ""),
                "creator": pdf_meta.get("creator", ""),
                "is_scanned": False,
                "scanned_pages_count": 0,
                "pages": []
            }

            for page_index in range(total_pages):
                page_number = page_index + 1
                page = doc[page_index]

                # Attempt direct text extraction
                raw_text = page.get_text("text").strip()

                is_page_scanned = False
                # If page contains fewer than 50 characters, it is likely scanned or image-based
                if len(raw_text) < 50:
                    logger.info(f"Page {page_number} has insufficient selectable text ({len(raw_text)} chars). Applying OCR/Vision...")
                    ocr_text = self._ocr_scanned_page(page, page_number)
                    if ocr_text and len(ocr_text.strip()) > len(raw_text):
                        raw_text = ocr_text.strip()
                        is_page_scanned = True
                        scanned_pages_count += 1
                
                # Format page block
                page_block = f"\n--- Page {page_number} ---\n{raw_text}"
                text_content_blocks.append(page_block)

                page_info = {
                    "page_number": page_number,
                    "char_count": len(raw_text),
                    "is_scanned": is_page_scanned
                }
                metadata["pages"].append(page_info)
                pages_data.append({
                    "page_number": page_number,
                    "text": raw_text,
                    "is_scanned": is_page_scanned
                })

            doc.close()

            metadata["scanned_pages_count"] = scanned_pages_count
            metadata["is_scanned"] = scanned_pages_count > (total_pages // 2)

            full_text = "\n".join(text_content_blocks).strip()

            if not full_text or len(full_text.replace("\n", "").strip()) == 0:
                raise ValueError("Could not extract readable text from the PDF. The document may be empty or unreadable.")

            logger.info(
                f"PDF parsed successfully: {total_pages} pages ({scanned_pages_count} scanned/OCR), "
                f"{len(full_text)} total characters"
            )

            return {
                "text_content": full_text,
                "metadata": metadata,
                "pages": pages_data
            }

        except Exception as e:
            logger.error(f"Failed to parse PDF {file_path}: {e}")
            raise

    def _ocr_scanned_page(self, page: fitz.Page, page_number: int) -> str:
        """Render scanned page to image and extract text via Gemini Vision / fitz OCR."""
        try:
            # Render page to pixmap
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")

            # Try Gemini Vision OCR first
            if settings.GOOGLE_API_KEY:
                import google.generativeai as genai
                genai.configure(api_key=settings.GOOGLE_API_KEY)
                for model_name in ["gemini-3.6-flash", "gemini-3.8-flash"]:
                    try:
                        model = genai.GenerativeModel(model_name)
                        resp = model.generate_content([
                            {"mime_type": "image/png", "data": png_bytes},
                            SCANNED_PAGE_PROMPT
                        ])
                        if resp and resp.text:
                            logger.info(f"OCR succeeded for page {page_number} via {model_name}")
                            return resp.text.strip()
                    except Exception as err:
                        logger.warning(f"OCR model {model_name} failed on page {page_number}: {err}")
                        continue

            # Fallback to PyMuPDF native OCR if Tesseract / OCR is present
            try:
                textpage_ocr = page.get_textpage_ocr(dpi=150, full=True)
                ocr_text = page.get_text("text", textpage=textpage_ocr)
                if ocr_text.strip():
                    return ocr_text.strip()
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Scanned page OCR failed for page {page_number}: {e}")

        # Return whatever minimal text was originally extracted
        return page.get_text("text").strip()


pdf_parser = PDFParser()
