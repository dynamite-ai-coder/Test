import logging
from typing import Optional
from functools import lru_cache


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with redaction filters."""
    logger = logging.getLogger(name)
    
    # Add redaction filter
    handler = logging.StreamHandler()
    handler.addFilter(RedactionFilter())
    
    if not logger.handlers:
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


class RedactionFilter(logging.Filter):
    """Filter to redact sensitive information from logs."""
    
    SENSITIVE_PATTERNS = [
        "password",
        "token",
        "secret",
        "api_key",
        "credential",
        "auth",
        "pwd",
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive fields from log record."""
        record.msg = self._redact(record.msg)
        
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(arg) for arg in record.args)
        
        return True
    
    def _redact(self, message: any) -> str:
        """Redact message string."""
        if not isinstance(message, str):
            return message
        
        msg = str(message)
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern.lower() in msg.lower():
                msg = msg.replace(msg, "[REDACTED]")
                break
        return msg
    
    def _redact_value(self, value: any) -> any:
        """Redact individual value if it looks sensitive."""
        if not isinstance(value, str):
            return value
        
        if any(pattern.lower() in str(value).lower() for pattern in self.SENSITIVE_PATTERNS):
            return "[REDACTED]"
        
        return value


class StructuredLogger:
    """Structured logging helper."""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def info(self, message: str, **kwargs):
        """Log info with structured data."""
        self.logger.info(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error with structured data."""
        self.logger.error(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning with structured data."""
        self.logger.warning(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug with structured data."""
        self.logger.debug(message, extra=kwargs)
