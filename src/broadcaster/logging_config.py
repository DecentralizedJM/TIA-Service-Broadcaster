"""
Logging configuration with security filters to mask sensitive data.
"""

import logging
import re
from typing import Any


class SecurityFilter(logging.Filter):
    """
    Filter to mask sensitive information in log messages.
    
    Masks:
    - Bot tokens (format: numbers:letters)
    - API secrets (long alphanumeric strings)
    - URLs containing tokens
    """
    
    # Pattern to match bot tokens: number:alphanumeric (e.g., 123456789:ABCdefGHI...)
    BOT_TOKEN_PATTERN = re.compile(r'\b\d{8,}:[A-Za-z0-9_-]{30,}\b')
    
    # Pattern to match API secrets (long alphanumeric strings)
    API_SECRET_PATTERN = re.compile(r'\b[A-Za-z0-9_-]{40,}\b')
    
    # Pattern to match URLs with tokens
    TOKEN_URL_PATTERN = re.compile(r'bot\d{8,}:[A-Za-z0-9_-]{30,}')
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and sanitize log record."""
        if hasattr(record, 'msg') and record.msg:
            # Convert to string if not already
            msg = str(record.msg)
            
            # Mask bot tokens
            msg = self.BOT_TOKEN_PATTERN.sub('[BOT_TOKEN_MASKED]', msg)
            msg = self.TOKEN_URL_PATTERN.sub('bot[BOT_TOKEN_MASKED]', msg)
            
            # Mask API secrets (but be careful not to mask everything)
            # Only mask if it looks like a secret (very long strings)
            # Skip common non-secret long strings
            if len(msg) > 50:  # Only check longer messages
                # Mask secrets but preserve structure
                msg = self.API_SECRET_PATTERN.sub(
                    lambda m: '[API_SECRET_MASKED]' if self._looks_like_secret(m.group()) else m.group(),
                    msg
                )
            
            # Update the record
            record.msg = msg
        
        # Also sanitize args if present
        if hasattr(record, 'args') and record.args:
            sanitized_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    arg = self.BOT_TOKEN_PATTERN.sub('[BOT_TOKEN_MASKED]', arg)
                    arg = self.TOKEN_URL_PATTERN.sub('bot[BOT_TOKEN_MASKED]', arg)
                sanitized_args.append(arg)
            record.args = tuple(sanitized_args)
        
        return True
    
    def _looks_like_secret(self, text: str) -> bool:
        """Check if a string looks like an API secret."""
        # Skip common non-secret patterns
        skip_patterns = [
            'HTTP/1.1',
            'WebSocket',
            'connection',
            'accepted',
            'closed',
            'signal',
            'SIG-',
            'sdk-',
        ]
        
        text_lower = text.lower()
        for pattern in skip_patterns:
            if pattern in text_lower:
                return False
        
        # If it's a very long alphanumeric string, likely a secret
        return len(text) >= 40 and text.replace('_', '').replace('-', '').isalnum()


def setup_secure_logging():
    """Set up logging with security filters."""
    # Get root logger
    root_logger = logging.getLogger()
    
    # Add security filter to root logger
    security_filter = SecurityFilter()
    root_logger.addFilter(security_filter)
    
    # Suppress verbose HTTP logging from httpx and httpcore
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    
    # Also add filter to these loggers
    for logger_name in ['httpx', 'httpcore', 'telegram', 'telegram.ext']:
        logger = logging.getLogger(logger_name)
        logger.addFilter(security_filter)
        logger.setLevel(logging.WARNING)
