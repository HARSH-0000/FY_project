"""
Document Validation Module
Enforces file format, size limits, page counts, magic byte verification, and security checks.
"""

from typing import Dict, Any, Tuple
import os
import fitz  # PyMuPDF
from app.core import settings, logger

# Magic numbers for supported formats
MAGIC_NUMBERS = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "webp": [b"RIFF"],  # also checks WEBP at offset 8
    "docx": [b"PK\x03\x04"],
}

class DocumentValidationError(Exception):
    """Exception raised when document validation fails."""
    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class DocumentValidator:
    """Validates files for security, format, size, and page limits."""

    def __init__(self):
        self.max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        self.allowed_types = [t.strip().lower() for t in settings.ALLOWED_FILE_TYPES.split(",")]
        self.max_pages = getattr(settings, "MAX_DOCUMENT_PAGES", 100)

    def validate_file(self, filename: str, content: bytes) -> Dict[str, Any]:
        """
        Validate file extension, size, magic signature, and integrity.
        
        Args:
            filename: Original name of the uploaded file
            content: Raw file bytes
            
        Returns:
            Dict containing validated metadata
        """
        if not filename or "." not in filename:
            raise DocumentValidationError("Invalid file name. Missing extension.", "INVALID_FILENAME")

        file_ext = filename.rsplit(".", 1)[-1].lower()

        # 1. Allowed file type check
        if file_ext not in self.allowed_types:
            raise DocumentValidationError(
                f"File type '.{file_ext}' is not supported. Supported formats: {', '.join(self.allowed_types)}",
                "UNSUPPORTED_TYPE"
            )

        # 2. File size check
        size_bytes = len(content)
        if size_bytes == 0:
            raise DocumentValidationError(f"File '{filename}' is empty.", "EMPTY_FILE")

        if size_bytes > self.max_size_bytes:
            max_mb = settings.MAX_UPLOAD_SIZE_MB
            actual_mb = round(size_bytes / (1024 * 1024), 2)
            raise DocumentValidationError(
                f"File '{filename}' ({actual_mb}MB) exceeds the maximum allowed size of {max_mb}MB.",
                "FILE_TOO_LARGE"
            )

        # 3. Magic byte signature verification
        self._verify_magic_signature(file_ext, content, filename)

        # 4. Detailed type-specific inspection
        page_count = 1
        if file_ext == "pdf":
            page_count = self._inspect_pdf(content, filename)
        elif file_ext in ["png", "jpg", "jpeg", "webp"]:
            self._inspect_image(content, filename)

        logger.info(f"File validated successfully: {filename} (type: {file_ext}, size: {size_bytes}B, pages: {page_count})")
        return {
            "filename": filename,
            "file_ext": file_ext,
            "size_bytes": size_bytes,
            "page_count": page_count,
            "is_image": file_ext in ["png", "jpg", "jpeg", "webp"],
            "is_pdf": file_ext == "pdf"
        }

    def _verify_magic_signature(self, file_ext: str, content: bytes, filename: str) -> None:
        """Inspect actual content bytes against known magic numbers."""
        if file_ext in MAGIC_NUMBERS:
            signatures = MAGIC_NUMBERS[file_ext]
            matched = any(content.startswith(sig) for sig in signatures)
            
            # Special check for WebP
            if file_ext == "webp":
                matched = content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP"

            if not matched:
                raise DocumentValidationError(
                    f"File '{filename}' content does not match its declared .{file_ext} format.",
                    "MAGIC_BYTE_MISMATCH"
                )
        elif file_ext == "txt":
            try:
                content[:2048].decode("utf-8")
            except UnicodeDecodeError:
                raise DocumentValidationError(
                    f"File '{filename}' is not a valid UTF-8 plain text file.",
                    "INVALID_TEXT_ENCODING"
                )

    def _inspect_pdf(self, content: bytes, filename: str) -> int:
        """Inspect PDF for encryption, corruption, and page limit."""
        try:
            doc = fitz.open(stream=content, filetype="pdf")
        except Exception as e:
            raise DocumentValidationError(
                f"PDF file '{filename}' is corrupted or cannot be read: {str(e)}",
                "CORRUPT_PDF"
            )

        try:
            if doc.is_encrypted:
                raise DocumentValidationError(
                    f"PDF file '{filename}' is password-protected or encrypted. Please remove the password to analyze.",
                    "ENCRYPTED_PDF"
                )

            page_count = len(doc)
            if page_count == 0:
                raise DocumentValidationError(f"PDF file '{filename}' contains no pages.", "EMPTY_PDF")

            if page_count > self.max_pages:
                raise DocumentValidationError(
                    f"PDF '{filename}' has {page_count} pages, exceeding the limit of {self.max_pages} pages.",
                    "EXCEEDS_PAGE_LIMIT"
                )

            return page_count
        finally:
            doc.close()

    def _inspect_image(self, content: bytes, filename: str) -> None:
        """Inspect image for readability via fitz."""
        try:
            doc = fitz.open(stream=content, filetype=filename.rsplit(".", 1)[-1].lower())
            if len(doc) == 0:
                raise DocumentValidationError(f"Image '{filename}' could not be decoded.", "CORRUPT_IMAGE")
            doc.close()
        except DocumentValidationError:
            raise
        except Exception as e:
            raise DocumentValidationError(f"Image file '{filename}' is invalid or corrupted: {str(e)}", "CORRUPT_IMAGE")


document_validator = DocumentValidator()
