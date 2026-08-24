from html.parser import HTMLParser
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class DOMExtractor(HTMLParser):
    """Extract simplified DOM structure for AI analysis."""
    
    def __init__(self):
        super().__init__()
        self.elements = []
        self.current_depth = 0
        self.max_depth = 3
    
    def handle_starttag(self, tag: str, attrs: list):
        """Process opening tag."""
        if self.current_depth > self.max_depth:
            return
        
        attrs_dict = dict(attrs)
        
        # Only capture relevant form elements
        if tag in ["input", "button", "select", "textarea", "form", "label"]:
            element_info = {
                "tag": tag,
                "id": attrs_dict.get("id", ""),
                "name": attrs_dict.get("name", ""),
                "type": attrs_dict.get("type", ""),
                "placeholder": attrs_dict.get("placeholder", ""),
                "aria-label": attrs_dict.get("aria-label", ""),
                "class": attrs_dict.get("class", ""),
                "value": attrs_dict.get("value", ""),
            }
            
            # Never include actual password values
            if element_info.get("type") == "password":
                element_info["value"] = "[PASSWORD]"
            
            self.elements.append(element_info)
        
        self.current_depth += 1
    
    def handle_endtag(self, tag: str):
        """Process closing tag."""
        if self.current_depth > 0:
            self.current_depth -= 1


class PageAnalyzer:
    """Analyze page content for login automation."""
    
    @staticmethod
    def extract_form_elements(html: str) -> str:
        """Extract form elements from HTML for AI analysis."""
        try:
            parser = DOMExtractor()
            parser.feed(html)
            
            # Build simplified DOM snapshot
            snapshot = "FORM ELEMENTS FOUND:\n"
            for i, elem in enumerate(parser.elements):
                snapshot += f"\nElement {i}:\n"
                for key, value in elem.items():
                    if value:
                        snapshot += f"  {key}: {value}\n"
            
            return snapshot if parser.elements else "No form elements found"
            
        except Exception as e:
            logger.error(f"Failed to extract form elements: {e}")
            return "Error analyzing page"
    
    @staticmethod
    def simplify_page_content(html: str, max_length: int = 5000) -> str:
        """Create simplified version of page for analysis."""
        try:
            # Remove script and style tags
            import re
            
            content = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
            
            # Remove HTML tags
            content = re.sub(r'<[^>]+>', ' ', content)
            
            # Remove excessive whitespace
            content = re.sub(r'\s+', ' ', content)
            
            # Truncate
            if len(content) > max_length:
                content = content[:max_length] + "..."
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"Failed to simplify page content: {e}")
            return ""
    
    @staticmethod
    def extract_page_text(html: str) -> str:
        """Extract visible text from page."""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text(separator=' ', strip=True)
            
            # Clean up
            import re
            text = re.sub(r'\s+', ' ', text)
            
            return text[:2000]  # Limit length
            
        except Exception as e:
            logger.warning(f"BeautifulSoup not available: {e}")
            return ""
