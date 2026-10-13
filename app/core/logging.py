import logging
import sys
from typing import Any
from app.core.config import settings


class PIISanitizingFilter(logging.Filter):
    """Filter that sanitizes log records to prevent PII leakage in logs."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            try:
                from app.services.pii_detector import pii_service
                record.msg = pii_service.sanitize_for_logging(record.msg)
            except Exception:
                pass
        return True


def setup_logging() -> logging.Logger:
    """Configure application logging."""
    
    # Create logger
    logger = logging.getLogger("irium")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Create console handler with utf-8 / replacement support for Windows
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Add PII Sanitization filter
    handler.addFilter(PIISanitizingFilter())
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return logger


# Global logger instance
logger = setup_logging()
