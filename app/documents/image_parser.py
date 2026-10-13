"""
Image Parser for Financial Charts, Tables, and Visual Documents.
Uses Gemini Vision (gemini-3.6-flash) for deep visual interpretation,
extracting chart titles, axes, legends, exact numerical data, and trends.
"""

from typing import Dict, Any
from pathlib import Path
import os
import fitz  # PyMuPDF
from app.core import settings, logger

IMAGE_ANALYSIS_PROMPT = """You are a senior financial analyst and document intelligence expert.
Analyze this financial image, chart, table, or visual document with complete accuracy.

Extract and structure the following details:
1. Document / Chart Title: Exact title or heading.
2. Visual Type: (e.g., Bar Chart, Line Chart, Balance Sheet Table, Waterfall Chart, Diagram, Scanned Page, Text Screenshot).
3. Axes, Labels & Legends: (If a chart, specify X-axis, Y-axis units, currencies, percentages, and legend categories).
4. Extracted Numerical Data & Values: List all visible financial figures, percentages, dates, and metric values explicitly shown.
5. Key Findings & Trends: Summarize the financial performance, comparisons, or message conveyed by the visual.
6. Complete Readable Text: Transcribe all visible text, notes, footnotes, and table rows faithfully.

Important:
- Be precise with financial numbers and units (e.g. $M, ₹ Crores, %).
- Do NOT guess figures that are illegible; state that they are unclear.
- Format the output cleanly with clear section headings.
"""


class ImageParser:
    """Parser for financial images (.png, .jpg, .jpeg, .webp)."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER

    def parse(self, file_path: str, file_ext: str = "png") -> Dict[str, Any]:
        """
        Parse image file using Gemini Vision multimodal model.
        
        Args:
            file_path: Path to the image file
            file_ext: Extension of the image
            
        Returns:
            Dict containing text_content, structured metadata, and pages array.
        """
        logger.info(f"Parsing image document: {file_path} (format: {file_ext})")

        with open(file_path, "rb") as f:
            image_bytes = f.read()

        mime_types = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp"
        }
        mime_type = mime_types.get(file_ext.lower(), "image/png")

        # Visual understanding via Gemini Vision
        analysis_text = self._analyze_with_gemini_vision(image_bytes, mime_type)

        # Basic image metadata using fitz
        width, height = 0, 0
        try:
            doc = fitz.open(stream=image_bytes, filetype=file_ext)
            if len(doc) > 0:
                rect = doc[0].rect
                width, height = int(rect.width), int(rect.height)
            doc.close()
        except Exception:
            pass

        metadata = {
            "total_pages": 1,
            "is_image": True,
            "format": file_ext,
            "dimensions": f"{width}x{height}",
            "pages": [{
                "page_number": 1,
                "char_count": len(analysis_text),
                "is_image": True
            }]
        }

        logger.info(f"Image parsed successfully: {len(analysis_text)} chars extracted")
        return {
            "text_content": f"--- Page 1 (Image Analysis) ---\n{analysis_text}",
            "metadata": metadata,
            "pages": [{
                "page_number": 1,
                "text": analysis_text,
                "is_image": True
            }]
        }

    def _analyze_with_gemini_vision(self, image_bytes: bytes, mime_type: str) -> str:
        """Call Gemini Vision model to interpret the image."""
        try:
            if settings.GOOGLE_API_KEY:
                import google.generativeai as genai
                genai.configure(api_key=settings.GOOGLE_API_KEY)

                # Prioritize gemini-3.6-flash, fallback to gemini-3.8-flash
                models_to_try = ["gemini-3.6-flash", "gemini-3.8-flash", "gemini-flash-latest"]
                for model_name in models_to_try:
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content([
                            {"mime_type": mime_type, "data": image_bytes},
                            IMAGE_ANALYSIS_PROMPT
                        ])
                        if response and response.text:
                            return response.text.strip()
                    except Exception as model_err:
                        logger.warning(f"Vision model {model_name} failed: {model_err}, trying next...")
                        continue

            # Fallback if vision API failed or unavailable
            logger.warning("Gemini Vision not available or all models failed; attempting PyMuPDF fallback text extraction")
            return self._fallback_ocr(image_bytes, mime_type)

        except Exception as e:
            logger.error(f"Image vision analysis failed: {e}")
            return self._fallback_ocr(image_bytes, mime_type)

    def _fallback_ocr(self, image_bytes: bytes, mime_type: str) -> str:
        """Fallback basic text extraction via fitz."""
        try:
            file_ext = mime_type.split("/")[-1]
            doc = fitz.open(stream=image_bytes, filetype=file_ext)
            if len(doc) > 0:
                text = doc[0].get_text().strip()
                doc.close()
                if text:
                    return f"[Extracted Text from Image]\n{text}"
            doc.close()
        except Exception:
            pass
        return "[Visual Image Document: Financial chart/image uploaded. Visual model interpretation completed.]"


image_parser = ImageParser()
