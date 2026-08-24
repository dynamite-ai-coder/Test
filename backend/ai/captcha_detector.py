import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CAPTCHADetector:
    """Detect CAPTCHA and anti-bot challenges."""
    
    CAPTCHA_INDICATORS = [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "i'm not a robot",
        "verify you are human",
        "prove you are human",
        "challenge",
        "bot check",
        "security check",
        "unusual activity",
        "unusual traffic",
        "blocked by cloudflare",
        "access denied",
        "403 forbidden",
        "429 too many requests",
        "rate limit",
    ]
    
    @staticmethod
    def detect_captcha(page_title: str, page_content: str, page_url: str) -> tuple[bool, Optional[str]]:
        """
        Detect if page contains CAPTCHA or anti-bot challenge.
        
        Returns:
            (detected: bool, reason: Optional[str])
        """
        content_lower = (page_title + " " + page_content + " " + page_url).lower()
        
        for indicator in CAPTCHADetector.CAPTCHA_INDICATORS:
            if indicator in content_lower:
                logger.warning(f"CAPTCHA detected: {indicator}")
                return True, f"CAPTCHA detected: {indicator}"
        
        # Check for common CAPTCHA iframe/script patterns
        if any(pattern in page_content for pattern in [
            "grecaptcha",
            "hcaptcha",
            "captcha-container",
            "_Recaptcha",
            "challenge-modal",
        ]):
            logger.warning("CAPTCHA frame detected in page content")
            return True, "CAPTCHA iframe/script detected"
        
        return False, None
    
    @staticmethod
    def is_likely_error_page(page_title: str, status_code: Optional[int] = None) -> bool:
        """Check if page is likely an error page."""
        error_indicators = [
            "error",
            "404",
            "403",
            "429",
            "500",
            "not found",
            "forbidden",
            "access denied",
            "timeout",
        ]
        
        page_title_lower = page_title.lower()
        
        if status_code and status_code >= 400:
            return True
        
        for indicator in error_indicators:
            if indicator in page_title_lower:
                return True
        
        return False
